from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.services.oss_upload_service import OSS_BUCKET_NAME, OSS_PATH_PREFIX, OssUploadWorker


class UploadProgressDialog(QDialog):
    def __init__(self, parent=None, run_dir: Path | None = None, log_callback=None) -> None:
        super().__init__(parent)
        self.run_dir = run_dir
        self.log_callback = log_callback or (lambda msg: None)
        self._last_logged_file = ""
        self.setWindowTitle("上传测试数据")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.title_label = QLabel("上传测试数据")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(self.title_label)

        self.oss_path_label = QLabel("")
        self.oss_path_label.setStyleSheet("color: #888; font-size: 12px;")
        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self._copy_oss_path)
        oss_path_row = QHBoxLayout()
        oss_path_row.addWidget(self.oss_path_label, 1)
        oss_path_row.addWidget(self.copy_btn)
        layout.addLayout(oss_path_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.file_progress_label = QLabel("正在上传: 0/0")
        layout.addWidget(self.file_progress_label)

        self.size_progress_label = QLabel("已上传: 0 B / 0 B")
        layout.addWidget(self.size_progress_label)

        self.time_label = QLabel("已耗时: 00:00:00  |  预计剩余: 00:00:00")
        layout.addWidget(self.time_label)

        self.current_file_progress_bar = QProgressBar()
        self.current_file_progress_bar.setRange(0, 100)
        self.current_file_progress_bar.setValue(0)
        layout.addWidget(self.current_file_progress_bar)

        self.current_file_label = QLabel("当前文件: ")
        layout.addWidget(self.current_file_label)

        self.uploaded_list = QTextEdit()
        self.uploaded_list.setReadOnly(True)
        self.uploaded_list.document().setMaximumBlockCount(1000)
        layout.addWidget(self.uploaded_list)

        self.action_btn = QPushButton("取消")
        self.action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_btn)

        # 去掉右上角的帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._upload_complete = False
        self._auto_close = False

    def set_auto_close(self, auto_close: bool) -> None:
        self._auto_close = auto_close

    def connect_worker(self, worker: OssUploadWorker) -> None:
        self.worker = worker
        worker.progress_updated.connect(self.on_progress_updated)
        worker.upload_finished.connect(self.on_upload_finished)
        worker.upload_error.connect(self.on_upload_error)
        # 拼接并显示 OSS 目标路径
        try:
            run_relative = str(worker.run_root.relative_to(worker.data_base_dir)).replace("\\", "/")
            oss_url = f"oss://{OSS_BUCKET_NAME}/{OSS_PATH_PREFIX}/{run_relative}"
        except Exception:
            oss_url = f"oss://{OSS_BUCKET_NAME}/{OSS_PATH_PREFIX}"
        self.oss_path_label.setText(f"上传地址: {oss_url}")

    def on_progress_updated(
        self,
        current_idx: int,
        total_count: int,
        uploaded_bytes: int,
        total_bytes: int,
        current_file: str,
        current_file_uploaded: int,
        current_file_total: int,
        elapsed_sec: float,
        remaining_sec: float,
    ) -> None:
        percent = int(uploaded_bytes * 100 / total_bytes) if total_bytes > 0 else 0
        self.progress_bar.setValue(percent)

        current_file_percent = (
            int(current_file_uploaded * 100 / current_file_total)
            if current_file_total > 0 else 0
        )
        self.current_file_progress_bar.setValue(current_file_percent)

        self.file_progress_label.setText(f"正在上传: {current_idx}/{total_count}")
        self.size_progress_label.setText(
            f"已上传: {self.format_size(uploaded_bytes)} / {self.format_size(total_bytes)}"
        )
        self.time_label.setText(
            f"已耗时: {self.format_time(elapsed_sec)}  |  预计剩余: {self.format_time(remaining_sec)}"
        )
        self.current_file_label.setText(
            f"当前文件: {current_file}  "
            f"({self.format_size(current_file_uploaded)} / {self.format_size(current_file_total)})"
        )
        existing = self.uploaded_list.toPlainText().splitlines()
        if current_file not in existing:
            self.uploaded_list.append(current_file)
        self.uploaded_list.ensureCursorVisible()

        # 文件切换时打印日志（使用绝对路径）
        if current_file and current_file != self._last_logged_file:
            self._last_logged_file = current_file
            if self.run_dir:
                abs_path = str(self.run_dir / current_file)
            else:
                abs_path = current_file
            self.log_callback(f"正在上传文件: {abs_path}")

    def on_upload_finished(self) -> None:
        self.title_label.setText("上传完成")
        self.file_progress_label.setText("上传完成")
        self.current_file_progress_bar.setVisible(False)
        self.current_file_label.setText("")
        self.action_btn.setText("关闭")
        self._upload_complete = True
        if self._auto_close:
            self.accept()

    def on_upload_error(self, error_msg: str) -> None:
        self.title_label.setText("上传出错")
        self.current_file_progress_bar.setVisible(False)
        self.current_file_label.setText(f"错误: {error_msg}")
        self.action_btn.setText("关闭")
        self._upload_complete = True
        self.log_callback(f"上传出错: {error_msg}")
        if self._auto_close:
            self.accept()

    def _on_action_clicked(self) -> None:
        if self._upload_complete:
            self.accept()
            return

        reply = QMessageBox.question(
            self,
            "取消上传",
            "上传尚未完成，确定要取消上传并关闭窗口吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._cleanup_worker(cancel=True)
            self.accept()

    def closeEvent(self, event) -> None:
        if self._upload_complete:
            self._cleanup_worker()
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "取消上传",
            "上传尚未完成，确定要取消上传并关闭窗口吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._cleanup_worker(cancel=True)
            event.accept()
        else:
            event.ignore()

    def _cleanup_worker(self, cancel: bool = False) -> None:
        if hasattr(self, 'worker') and self.worker:
            try:
                self.worker.progress_updated.disconnect(self.on_progress_updated)
                self.worker.upload_finished.disconnect(self.on_upload_finished)
                self.worker.upload_error.disconnect(self.on_upload_error)
            except Exception:
                pass
            if cancel:
                self.worker.stop()
            elif self.worker.isRunning():
                self.worker.quit()
                self.worker.wait(3000)

    @staticmethod
    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _copy_oss_path(self) -> None:
        oss_text = self.oss_path_label.text()
        # 去掉前缀，只保留 oss:// 地址
        if "上传地址: " in oss_text:
            oss_text = oss_text.replace("上传地址: ", "")
        # 地址末尾补充 /
        if not oss_text.endswith("/"):
            oss_text += "/"
        QApplication.clipboard().setText(oss_text)
        QMessageBox.information(self, "复制成功", "OSS 上传地址已复制到剪切板")

    @staticmethod
    def format_time(seconds: float) -> str:
        total = int(seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
