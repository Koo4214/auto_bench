from __future__ import annotations

import os
import time
from pathlib import Path

try:
    import oss2
except ImportError:
    oss2 = None

from PyQt5.QtCore import QThread, pyqtSignal

OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
OSS_ENDPOINT = "oss-cn-wulanchabu.aliyuncs.com"
OSS_BUCKET_NAME = "public-hq-data-upload"
OSS_PATH_PREFIX = "benchmark_data"


def _has_oss_credentials() -> bool:
    return bool(OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET)


def check_run_uploaded(run_dir: Path, base_dir: Path) -> bool:
    """查询 OSS 判断指定 run 目录是否已上传（存在 UPLOAD_COMPLETED 标记）。"""
    if oss2 is None:
        return False
    if not _has_oss_credentials():
        return False
    try:
        auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
        run_relative = str(run_dir.relative_to(base_dir)).replace("\\", "/")
        completed_key = f"{OSS_PATH_PREFIX}/{run_relative}/UPLOAD_COMPLETED"
        return bucket.object_exists(completed_key)
    except Exception:
        return False


class OssUploadWorker(QThread):
    # (当前文件序号, 总文件数, 已上传字节, 总字节, 当前文件名,
    #  当前文件已上传字节, 当前文件总字节, 已耗时秒, 估计剩余秒)
    progress_updated = pyqtSignal(int, int, int, int, str, int, int, float, float)
    upload_finished = pyqtSignal()
    upload_error = pyqtSignal(str)

    def __init__(self, run_root: Path, data_base_dir: Path) -> None:
        super().__init__()
        self.run_root = run_root
        self.data_base_dir = data_base_dir
        self.finished.connect(self.deleteLater)
        self._should_stop = False
        self._uploaded_bytes = 0
        self._current_file_uploaded = 0
        self._last_progress_time = 0.0
        self._start_time = 0.0
        self._total_size = 0
        self._total_count = 0
        self._current_idx = 0
        self._current_file_name = ""
        self._current_file_total = 0

    def stop(self) -> None:
        self._should_stop = True

    def _emit_progress(self) -> None:
        elapsed = time.time() - self._start_time
        uploaded = self._uploaded_bytes + self._current_file_uploaded
        if uploaded > 0 and self._total_size > 0:
            rate = uploaded / self._total_size
            remaining = elapsed / rate - elapsed if rate > 0 else 0.0
        else:
            remaining = 0.0
        self.progress_updated.emit(
            self._current_idx,
            self._total_count,
            uploaded,
            self._total_size,
            self._current_file_name,
            self._current_file_uploaded,
            self._current_file_total,
            elapsed,
            max(0.0, remaining),
        )

    def _progress_callback(self, bytes_consumed: int, total_bytes: int) -> None:
        self._current_file_uploaded = bytes_consumed
        self._current_file_total = total_bytes
        now = time.time()
        if now - self._last_progress_time >= 1.0:
            self._emit_progress()
            self._last_progress_time = now

    def run(self) -> None:
        if oss2 is None:
            self.upload_error.emit("oss2 模块未安装，请执行 pip install oss2")
            return
        if not _has_oss_credentials():
            self.upload_error.emit("请设置 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET 环境变量")
            return
        try:
            files: list[tuple[Path, int]] = []
            total_size = 0
            seen_names: set[str] = set()
            for f in self.run_root.rglob("*"):
                if f.is_file():
                    if f.name in seen_names:
                        continue
                    seen_names.add(f.name)
                    size = f.stat().st_size
                    files.append((f, size))
                    total_size += size

            self._total_count = len(files)
            if self._total_count == 0:
                self.upload_finished.emit()
                return

            self._total_size = total_size
            self._start_time = time.time()
            self._uploaded_bytes = 0

            auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
            bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

            for idx, (file_path, file_size) in enumerate(files, start=1):
                if self._should_stop:
                    break

                try:
                    relative_path = file_path.relative_to(self.data_base_dir)
                except ValueError:
                    relative_path = file_path.name

                oss_key = f"{OSS_PATH_PREFIX}/{str(relative_path).replace(chr(92), '/')}"

                self._current_idx = idx
                self._current_file_name = str(file_path.relative_to(self.run_root))
                self._current_file_total = file_size
                self._current_file_uploaded = 0
                self._last_progress_time = time.time()

                bucket.put_object_from_file(
                    oss_key,
                    str(file_path),
                    progress_callback=self._progress_callback,
                )

                # 为上传的文件设置 noarchive=true 标签
                tagging_rule = oss2.models.TaggingRule()
                tagging_rule.add("noarchive", "true")
                tagging = oss2.models.Tagging(tagging_rule)
                bucket.put_object_tagging(oss_key, tagging)

                self._uploaded_bytes += file_size
                self._current_file_uploaded = 0
                self._emit_progress()

            if not self._should_stop:
                # 在 OSS 远程目录创建上传完成标记文件
                run_relative = self.run_root.relative_to(self.data_base_dir)
                completed_key = f"{OSS_PATH_PREFIX}/{str(run_relative).replace(chr(92), '/')}/UPLOAD_COMPLETED"
                bucket.put_object(completed_key, b"")

            self.upload_finished.emit()

        except Exception as e:
            self.upload_error.emit(str(e))
