from __future__ import annotations

import os
import shutil
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    import oss2
except ImportError:
    oss2 = None

from src.services.oss_upload_service import (
    OssUploadWorker,
    check_run_uploaded,
)
from src.ui.widgets.upload_progress_dialog import UploadProgressDialog


class RunItemWidget(QWidget):
    def __init__(self, run_dir: Path, base_dir: Path, is_uploaded: bool = False, parent=None, log_callback=None) -> None:
        super().__init__(parent)
        self.run_dir = run_dir
        self.base_dir = base_dir
        self._is_uploaded = is_uploaded
        self.log_callback = log_callback or (lambda msg: None)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.check_box = QCheckBox()
        self.check_box.setChecked(False)
        self.check_box.setEnabled(not is_uploaded)
        layout.addWidget(self.check_box)

        info_layout = QVBoxLayout()
        self.name_label = QLabel(run_dir.name)
        self.name_label.setStyleSheet("font-weight: 600;")
        info_layout.addWidget(self.name_label)

        self.size_label = QLabel(self._format_size(self._get_dir_size(run_dir)))
        self.size_label.setStyleSheet("color: #666; font-size: 12px;")
        info_layout.addWidget(self.size_label)

        layout.addLayout(info_layout, 1)

        self.upload_btn = QPushButton("上传")
        self.delete_btn = QPushButton("删除")
        layout.addWidget(self.upload_btn)
        layout.addWidget(self.delete_btn)

        self.upload_btn.clicked.connect(self._on_upload)
        self.delete_btn.clicked.connect(self._on_delete)

        self._refresh_upload_status()

    def _get_dir_size(self, path: Path) -> int:
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += self._get_dir_size(Path(entry.path))
        except OSError:
            pass
        return total

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _on_upload(self) -> None:
        self.log_callback(f"开始上传 Run: {self.run_dir}")
        dialog = UploadProgressDialog(self, run_dir=self.run_dir, log_callback=self.log_callback)
        worker = OssUploadWorker(self.run_dir, self.base_dir)
        dialog.connect_worker(worker)
        worker.start()
        dialog.exec_()
        self._refresh_size()
        # 直接查询 OSS 真实上传状态，不依赖 dialog 内部标志
        self._is_uploaded = check_run_uploaded(self.run_dir, self.base_dir)
        self._refresh_upload_status()
        if self._is_uploaded:
            self.log_callback(f"Run 上传完成: {self.run_dir}")
        else:
            self.log_callback(f"Run 上传未完成或失败: {self.run_dir}")

    def set_checked(self, checked: bool) -> None:
        self.check_box.setChecked(checked)

    def is_checked(self) -> bool:
        return self.check_box.isChecked()

    def set_batch_mode(self, batch: bool) -> None:
        """批量模式隐藏复选框。"""
        self.check_box.setVisible(not batch)

    def set_uploaded(self, uploaded: bool) -> None:
        self._is_uploaded = uploaded
        self._refresh_upload_status()
        self.check_box.setEnabled(not uploaded)
        if uploaded:
            self.set_checked(False)

    def get_run_dir(self) -> Path:
        return self.run_dir

    def _refresh_upload_status(self) -> None:
        if self._is_uploaded:
            self.upload_btn.setText("已上传")
            self.upload_btn.setEnabled(False)
        else:
            self.upload_btn.setText("上传")
            self.upload_btn.setEnabled(True)

    def _on_delete(self) -> None:
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除目录 {self.run_dir.name} 吗？\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                shutil.rmtree(self.run_dir)
                # 向上最多清理 2 级空父目录
                current = self.run_dir.parent
                for _ in range(2):
                    if current.exists() and not any(current.iterdir()):
                        current.rmdir()
                        current = current.parent
                    else:
                        break
                self.setVisible(False)
                self.deleteLater()
            except Exception as e:
                QMessageBox.critical(self, "删除失败", f"删除目录失败: {e}")

    def _refresh_size(self) -> None:
        size = self._get_dir_size(self.run_dir)
        self.size_label.setText(self._format_size(size))


class DataManagementDialog(QDialog):
    def __init__(self, base_dir: Path, parent=None, log_callback=None) -> None:
        super().__init__(parent)
        self.base_dir = Path(base_dir)
        self.log_callback = log_callback or (lambda msg: None)
        self.setWindowTitle("数据管理")
        self.setMinimumWidth(780)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QLabel("Run 数据管理")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(header)

        self.path_label = QLabel(f"基目录: {self.base_dir}")
        self.path_label.setStyleSheet("color: #666;")
        layout.addWidget(self.path_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(4)
        self.content_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self.load_runs)
        btn_row.addWidget(self.refresh_btn)

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("取消全选")
        self.select_none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(self.select_none_btn)

        self.batch_upload_btn = QPushButton("批量上传")
        self.batch_upload_btn.clicked.connect(self._batch_upload)
        self.batch_upload_btn.setStyleSheet("font-weight: 600;")
        btn_row.addWidget(self.batch_upload_btn)

        layout.addLayout(btn_row)

        self._run_items: list[RunItemWidget] = []

        self.load_runs()

    def load_runs(self) -> None:
        self._run_items.clear()
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        run_dirs = self._find_run_dirs()
        if not run_dirs:
            empty_label = QLabel("未找到 run 数据目录")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #999; padding: 40px;")
            self.content_layout.addWidget(empty_label)
            return

        for run_dir in sorted(run_dirs, key=lambda p: p.name, reverse=True):
            is_uploaded = self._is_run_uploaded(run_dir)
            item = RunItemWidget(run_dir, self.base_dir, is_uploaded, self, log_callback=self.log_callback)
            self._run_items.append(item)
            self.content_layout.addWidget(item)

    def _select_all(self) -> None:
        for item in self._run_items:
            item.set_checked(True)

    def _select_none(self) -> None:
        for item in self._run_items:
            item.set_checked(False)

    def _batch_upload(self) -> None:
        items = [item for item in self._run_items if item.is_checked() and not item._is_uploaded]
        if not items:
            QMessageBox.information(self, "批量上传", "没有选中的待上传 Run 目录。")
            return

        failed = []
        for item in items:
            run_dir = item.get_run_dir()
            self.log_callback(f"开始上传 Run: {run_dir}")
            dialog = UploadProgressDialog(self, run_dir=run_dir, log_callback=self.log_callback)
            dialog.set_auto_close(True)
            worker = OssUploadWorker(run_dir, self.base_dir)
            dialog.connect_worker(worker)
            worker.start()
            dialog.exec_()
            item._refresh_size()
            uploaded = check_run_uploaded(run_dir, self.base_dir)
            item.set_uploaded(uploaded)
            if uploaded:
                self.log_callback(f"Run 上传完成: {run_dir}")
            else:
                self.log_callback(f"Run 上传未完成或失败: {run_dir}")
                failed.append(run_dir.name)

        if failed:
            QMessageBox.warning(
                self, "批量上传完成",
                f"上传完成，以下 Run 上传失败或未完成:\n\n" + "\n".join(failed)
            )
        else:
            QMessageBox.information(self, "批量上传完成", f"全部 {len(items)} 个 Run 已上传完成！")

    def _is_run_uploaded(self, run_dir: Path) -> bool:
        """查询 OSS 判断该 run 是否已上传。"""
        return check_run_uploaded(run_dir, self.base_dir)

    def _find_run_dirs(self) -> list[Path]:
        run_dirs: list[Path] = []
        base = self.base_dir
        if not base.exists():
            return run_dirs

        for date_dir in base.iterdir():
            if not date_dir.is_dir():
                continue
            for vehicle_dir in date_dir.iterdir():
                if not vehicle_dir.is_dir():
                    continue
                for run_dir in vehicle_dir.iterdir():
                    if run_dir.is_dir():
                        run_dirs.append(run_dir)

        return run_dirs
