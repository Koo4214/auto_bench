from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.app.runtime_tools import get_app_root, resolve_ffmpeg_path
from src.domain.test_functions import TEST_FUNCTION_OPTIONS, normalize_test_function
from src.ui.widgets.data_management_dialog import DataManagementDialog


class RunSetupPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("设置")
        layout.addWidget(title)

        form_layout = QFormLayout()
        self.output_path = QLineEdit(str(get_app_root() / "data"))
        self.output_browse_btn = QPushButton("浏览")
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_path)
        output_row.addWidget(self.output_browse_btn)
        output_container = QWidget()
        output_container.setLayout(output_row)

        self.ffmpeg_path = QLineEdit("")
        self.ffmpeg_path.setPlaceholderText("留空则使用软件内置 FFmpeg")
        self.ffmpeg_browse_btn = QPushButton("浏览")
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(self.ffmpeg_path)
        ffmpeg_row.addWidget(self.ffmpeg_browse_btn)
        ffmpeg_container = QWidget()
        ffmpeg_container.setLayout(ffmpeg_row)

        self.test_function = QComboBox()
        self.test_function.addItems(TEST_FUNCTION_OPTIONS)
        self.test_date = QLineEdit(datetime.now().strftime("%Y-%m-%d"))
        self.vehicle_model = QLineEdit("ProbeVehicle")
        self.vehicle_id = QLineEdit("TEST001")
        self.version = QLineEdit("unknown")
        self.tester = QLineEdit("operator")
        self.city = QLineEdit("Shanghai")
        self.route = QLineEdit("")
        self.weather = QLineEdit("Sunny")
        self.day_night = QLineEdit("Day")
        for label, field in [
            ("测试功能", self.test_function),
            ("输出路径", output_container),
            ("FFmpeg 路径", ffmpeg_container),
            ("测试日期", self.test_date),
            ("车型", self.vehicle_model),
            ("车牌/编号", self.vehicle_id),
            ("竞品版本", self.version),
            ("测试员", self.tester),
            ("城市", self.city),
            ("路线", self.route),
            ("天气", self.weather),
            ("昼夜", self.day_night),
        ]:
            form_layout.addRow(label, field)
        layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        self.next_btn = QPushButton("下一步")
        self.save_config_btn = QPushButton("保存设置")
        self.playback_btn = QPushButton("回放 / 编辑")
        self.data_mgmt_btn = QPushButton("数据管理")
        button_row.addWidget(self.next_btn)
        button_row.addWidget(self.save_config_btn)
        button_row.addWidget(self.playback_btn)
        button_row.addWidget(self.data_mgmt_btn)
        layout.addLayout(button_row)

        self.status_label = QLabel("状态：等待填写 run 信息")
        layout.addWidget(self.status_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.output_browse_btn.clicked.connect(self.choose_output_path)
        self.ffmpeg_browse_btn.clicked.connect(self.choose_ffmpeg_path)
        self.data_mgmt_btn.clicked.connect(self.open_data_management)
        self.save_config_btn.clicked.connect(self.save_config)

        # 启动时加载已有配置
        self.load_config()

    def open_data_management(self) -> None:
        base_dir = Path(self.output_path_value())
        dialog = DataManagementDialog(base_dir, self, log_callback=self.append_log)
        dialog.exec_()

    def choose_output_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            self.output_path.text().strip(),
        )
        if directory:
            self.output_path.setText(directory)

    def choose_ffmpeg_path(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 FFmpeg 可执行文件",
            self.ffmpeg_path.text().strip() or str(get_app_root()),
            "可执行文件 (*.exe);;所有文件 (*)",
        )
        if file_path:
            self.ffmpeg_path.setText(file_path)

    @staticmethod
    def _is_under(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def load_config(self) -> None:
        config_file = get_app_root() / "config.json"
        if not config_file.exists():
            return
        try:
            with config_file.open("r", encoding="utf-8") as f:
                config = json.load(f)
            self.output_path.setText(config.get("output_path", self.output_path.text()))
            configured_ffmpeg = config.get("ffmpeg_path", "").strip()
            bundled_ffmpeg = resolve_ffmpeg_path()
            if (
                configured_ffmpeg
                and Path(configured_ffmpeg).exists()
                and not (
                    bundled_ffmpeg
                    and self._is_under(Path(bundled_ffmpeg), get_app_root())
                )
            ):
                self.ffmpeg_path.setText(configured_ffmpeg)
            else:
                self.ffmpeg_path.setText("")
            self.set_test_function(config.get("test_function", ""))
            self.vehicle_model.setText(config.get("vehicle_model", self.vehicle_model.text()))
            self.vehicle_id.setText(config.get("vehicle_id", self.vehicle_id.text()))
            self.version.setText(config.get("version", self.version.text()))
            self.tester.setText(config.get("tester", self.tester.text()))
            self.city.setText(config.get("city", self.city.text()))
        except Exception as exc:
            self.append_log(f"加载配置失败: {exc}")

    def _build_config(self) -> dict[str, str]:
        return {
            "output_path": self.output_path.text().strip(),
            "ffmpeg_path": self.ffmpeg_path.text().strip(),
            "test_function": self.test_function_value(),
            "vehicle_model": self.vehicle_model.text().strip(),
            "vehicle_id": self.vehicle_id.text().strip(),
            "version": self.version.text().strip(),
            "tester": self.tester.text().strip(),
            "city": self.city.text().strip(),
        }

    def save_config(self) -> None:
        config = self._build_config()
        config_file = get_app_root() / "config.json"
        try:
            with config_file.open("w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "保存成功", f"设置已保存到 {config_file}")
            self.append_log(f"配置已保存到 {config_file}")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"保存配置失败: {exc}")

    def save_config_silent(self) -> bool:
        """静默保存配置，不弹窗，返回是否成功。"""
        config = self._build_config()
        config_file = get_app_root() / "config.json"
        try:
            with config_file.open("w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def ffmpeg_path_value(self) -> str:
        return self.ffmpeg_path.text().strip()

    def set_test_function(self, value: object) -> None:
        test_function = normalize_test_function(value)
        index = self.test_function.findText(test_function)
        if index >= 0:
            self.test_function.setCurrentIndex(index)

    def test_function_value(self) -> str:
        return normalize_test_function(self.test_function.currentText())

    def collect_form(self) -> Dict[str, str]:
        return {
            "test_function": self.test_function_value(),
            "test_date": self.test_date.text().strip(),
            "vehicle_model": self.vehicle_model.text().strip(),
            "vehicle_id": self.vehicle_id.text().strip(),
            "competitor_version": self.version.text().strip(),
            "tester": self.tester.text().strip(),
            "city": self.city.text().strip(),
            "route": self.route.text().strip(),
            "weather": self.weather.text().strip(),
            "day_night": self.day_night.text().strip(),
        }

    def output_path_value(self) -> str:
        output_path = self.output_path.text().strip()
        if not output_path:
            return str(get_app_root() / "data")
        path = Path(output_path).expanduser()
        if not path.is_absolute():
            path = get_app_root() / path
        return str(path)

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        self.log_output.append(f"[{timestamp}] {message}")
