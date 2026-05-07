from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import List

from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CalibrationPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QHBoxLayout(self)

        left = QWidget()
        left.setMaximumWidth(900)
        left_layout = QVBoxLayout(left)
        root.addWidget(left, 3)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        root.addWidget(right, 2)

        left_layout.addWidget(QLabel("传感器校准"))

        form_layout = QFormLayout()
        self.rtk_serial_port = QComboBox()
        self.rtk_baudrate = QLineEdit("230400")
        self.test_function = QComboBox()
        self.test_function.addItems([
            "行车-外部路测试",
            "行车-园区测试",
            "行车-高速测试",
            "泊车测试",
            "主动安全测试",
        ])
        self.imu_address = QLineEdit("")
        self.scan_imu_btn = QPushButton("扫描蓝牙 IMU")
        imu_address_row = QHBoxLayout()
        imu_address_row.setContentsMargins(0, 0, 0, 0)
        imu_address_row.addWidget(self.imu_address, 1)
        imu_address_row.addWidget(self.scan_imu_btn)
        imu_address_widget = QWidget()
        imu_address_widget.setLayout(imu_address_row)

        self.imu_device_combo = QComboBox()
        self.imu_device_combo.addItem("请先扫描蓝牙 IMU", "")
        self.imu_device_combo.currentIndexChanged.connect(self._apply_selected_imu_address)

        self.imu_axis = QComboBox()
        self.imu_axis.addItems(["X", "Y", "Z"])
        self.imu_axis.setCurrentText("Z")
        self.imu_direction = QComboBox()
        self.imu_direction.addItem("正向", False)
        self.imu_direction.addItem("反向", True)
        self.camera1 = QComboBox()
        self.camera2 = QComboBox()
        self.sample_replay_dir = QLineEdit()
        self.sample_replay_browse_btn = QPushButton("浏览样例")
        sample_row = QHBoxLayout()
        sample_row.setContentsMargins(0, 0, 0, 0)
        sample_row.addWidget(self.sample_replay_dir, 1)
        sample_row.addWidget(self.sample_replay_browse_btn)
        sample_widget = QWidget()
        sample_widget.setLayout(sample_row)
        for label, field in [
            ("测试功能", self.test_function),
            ("RTK 串口", self.rtk_serial_port),
            ("RTK 波特率", self.rtk_baudrate),
            ("IMU 蓝牙地址", imu_address_widget),
            ("扫描结果", self.imu_device_combo),
            ("IMU 方向盘轴", self.imu_axis),
            ("方向取反", self.imu_direction),
            ("样例回放目录", sample_widget),
            ("摄像头 1", self.camera1),
            ("摄像头 2", self.camera2),
        ]:
            form_layout.addRow(label, field)
        left_layout.addLayout(form_layout)

        control_row = QHBoxLayout()

        # 串口下拉按钮组
        self.serial_menu_btn = QToolButton()
        self.serial_menu_btn.setText("串口")
        self.serial_menu_btn.setPopupMode(QToolButton.InstantPopup)
        serial_menu = QMenu(self.serial_menu_btn)
        self.refresh_serial_action = QAction("刷新串口", self)
        serial_menu.addAction(self.refresh_serial_action)
        self.serial_menu_btn.setMenu(serial_menu)

        # 摄像头下拉按钮组
        self.camera_menu_btn = QToolButton()
        self.camera_menu_btn.setText("摄像头")
        self.camera_menu_btn.setPopupMode(QToolButton.InstantPopup)
        camera_menu = QMenu(self.camera_menu_btn)
        self.refresh_cameras_action = QAction("刷新摄像头", self)
        self.preview_action = QAction("启动预览", self)
        self.preview_stop_action = QAction("停止预览", self)
        camera_menu.addAction(self.refresh_cameras_action)
        camera_menu.addAction(self.preview_action)
        camera_menu.addAction(self.preview_stop_action)
        self.camera_menu_btn.setMenu(camera_menu)

        # IMU 下拉按钮组
        self.imu_menu_btn = QToolButton()
        self.imu_menu_btn.setText("IMU")
        self.imu_menu_btn.setPopupMode(QToolButton.InstantPopup)
        imu_menu = QMenu(self.imu_menu_btn)
        self.imu_start_action = QAction("启动 IMU", self)
        self.imu_stop_action = QAction("停止 IMU", self)
        self.imu_zero_action = QAction("设置 IMU 零点", self)
        imu_menu.addAction(self.imu_start_action)
        imu_menu.addAction(self.imu_stop_action)
        imu_menu.addAction(self.imu_zero_action)
        self.imu_menu_btn.setMenu(imu_menu)

        # RTK 下拉按钮组
        self.rtk_menu_btn = QToolButton()
        self.rtk_menu_btn.setText("RTK")
        self.rtk_menu_btn.setPopupMode(QToolButton.InstantPopup)
        rtk_menu = QMenu(self.rtk_menu_btn)
        self.rtk_start_action = QAction("启动 RTK", self)
        self.rtk_stop_action = QAction("停止 RTK", self)
        rtk_menu.addAction(self.rtk_start_action)
        rtk_menu.addAction(self.rtk_stop_action)
        self.rtk_menu_btn.setMenu(rtk_menu)

        self.self_check_btn = QPushButton("运行自检")
        for button in [
            self.serial_menu_btn,
            self.camera_menu_btn,
            self.imu_menu_btn,
            self.rtk_menu_btn,
            self.self_check_btn,
        ]:
            control_row.addWidget(button)
        left_layout.addLayout(control_row)

        nav_row = QHBoxLayout()
        self.back_btn = QPushButton("返回")
        self.start_test_btn = QPushButton("开始测试")
        nav_row.addWidget(self.back_btn)
        nav_row.addWidget(self.start_test_btn)
        left_layout.addLayout(nav_row)

        grid = QGridLayout()
        self.self_check_label = QLabel("自检：未执行")
        self.self_check_detail = QLabel("检查项：暂无")
        self.self_check_detail.setWordWrap(True)
        self.rtk_label = QLabel("RTK：空闲")
        self.imu_label = QLabel("IMU：空闲")
        self.camera1_label = QLabel("摄像头 1：空闲")
        self.camera2_label = QLabel("摄像头 2：空闲")
        self.imu_angles_label = QLabel("Angle X: - | Angle Y: - | Angle Z: -")
        self.imu_extra_label = QLabel("方向盘角度：- | Gyro Z: - | 样本时间：-")
        grid.addWidget(self.self_check_label, 0, 0)
        grid.addWidget(self.self_check_detail, 0, 1, 1, 2)
        grid.addWidget(self.rtk_label, 1, 0)
        grid.addWidget(self.imu_label, 1, 1)
        grid.addWidget(self.camera1_label, 2, 0)
        grid.addWidget(self.camera2_label, 2, 1)
        grid.addWidget(self.imu_angles_label, 3, 0, 1, 2)
        grid.addWidget(self.imu_extra_label, 4, 0, 1, 2)
        left_layout.addLayout(grid)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output)

        right_layout.addWidget(QLabel("校准预览"))
        self.camera_view_1 = self._build_viewfinder()
        self.camera_view_2 = self._build_viewfinder()
        right_layout.addWidget(self.camera_view_1, 1)
        right_layout.addWidget(self.camera_view_2, 1)

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        self.log_output.append(f"[{timestamp}] {message}")

    def selected_camera_devices(self) -> List[str]:
        selected = [self.camera1.currentData(), self.camera2.currentData()]
        return [item for item in selected if item]

    def set_serial_options(self, ports: List[str]) -> None:
        previous = self.rtk_serial_port.currentData() or self.rtk_serial_port.currentText()
        self.rtk_serial_port.clear()
        if not ports:
            self.rtk_serial_port.addItem("未发现串口", "")
            return
        for port in ports:
            self.rtk_serial_port.addItem(port, port)
        if previous:
            index = self.rtk_serial_port.findData(previous)
            if index >= 0:
                self.rtk_serial_port.setCurrentIndex(index)
                return
        default_index = self.rtk_serial_port.findData("COM3")
        if default_index >= 0:
            self.rtk_serial_port.setCurrentIndex(default_index)
        else:
            self.rtk_serial_port.setCurrentIndex(0)

    def rtk_serial_port_value(self) -> str:
        value = self.rtk_serial_port.currentData()
        if value:
            return value
        text = self.rtk_serial_port.currentText().strip()
        if text and text not in {"?????", "No serial ports", "未发现串口"}:
            return text
        return "COM3"

    def test_function_value(self) -> str:
        return self.test_function.currentText().strip() or "行车-外部路测试"

    def rtk_serial_baudrate_value(self) -> int:
        try:
            return int(self.rtk_baudrate.text().strip() or "230400")
        except ValueError:
            return 230400

    def imu_address_value(self):
        value = self.imu_address.text().strip()
        return value or None

    def imu_axis_value(self) -> str:
        return self.imu_axis.currentText()

    def imu_inverted_value(self) -> bool:
        return bool(self.imu_direction.currentData())

    def sample_replay_dir_value(self):
        value = self.sample_replay_dir.text().strip()
        return value or None

    def browse_sample_replay_dir(self) -> None:
        start_dir = self.sample_replay_dir.text().strip() or str(Path.cwd())
        selected_dir = QFileDialog.getExistingDirectory(self, "选择样例回放目录", start_dir)
        if selected_dir:
            self.sample_replay_dir.setText(selected_dir)

    def set_camera_options(self, cameras: List[dict]) -> None:
        selected_before = [self.camera1.currentData(), self.camera2.currentData()]
        for combo in (self.camera1, self.camera2):
            combo.clear()
            combo.addItem("请选择", "")
        for camera in cameras:
            label = f"{camera['description']} | {camera['device_name']}"
            self.camera1.addItem(label, camera['device_name'])
            self.camera2.addItem(label, camera['device_name'])
        defaults = self._default_camera_indices(cameras)
        self._restore_or_default(self.camera1, selected_before[0], defaults[0])
        self._restore_or_default(self.camera2, selected_before[1], defaults[1])

    def set_imu_device_options(self, devices: List[dict]) -> None:
        selected_before = self.imu_address.text().strip()
        self.imu_device_combo.blockSignals(True)
        self.imu_device_combo.clear()
        if not devices:
            self.imu_device_combo.addItem("未扫描到 WT 系列 IMU", "")
            self.imu_device_combo.blockSignals(False)
            return
        for device in devices:
            label = f"{device['name']} | {device['address']}"
            self.imu_device_combo.addItem(label, device['address'])
        selected_index = 0
        if selected_before:
            matched_index = self.imu_device_combo.findData(selected_before)
            if matched_index >= 0:
                selected_index = matched_index
        self.imu_device_combo.setCurrentIndex(selected_index)
        self.imu_device_combo.blockSignals(False)
        self._apply_selected_imu_address(selected_index)

    def set_imu_scan_busy(self, busy: bool) -> None:
        self.scan_imu_btn.setEnabled(not busy)
        self.scan_imu_btn.setText("扫描中..." if busy else "扫描蓝牙 IMU")

    def apply_self_check_report(self, report: dict) -> None:
        label_map = {"pass": "通过", "warn": "警告", "fail": "失败"}
        self.self_check_label.setText(f"自检：{label_map[report['overall']]}")
        detail = " | ".join(
            f"{item['label']}={label_map[item['level']]}" for item in report['checks']
        )
        self.self_check_detail.setText(f"检查项：{detail}")

    def apply_snapshot(self, snapshot: dict) -> None:
        rtk_state = "已连接" if snapshot.get("rtk_connected") else "未连接"
        if snapshot.get("rtk_error"):
            rtk_state += f" 错误={snapshot['rtk_error']}"
        self.rtk_label.setText(f"RTK：{rtk_state}")

        phase = snapshot.get("imu_phase")
        axis = snapshot.get("imu_axis", "Z")
        direction = "反向" if snapshot.get("imu_inverted") else "正向"
        angle = snapshot.get("imu_angle")
        if phase == "streaming":
            imu_state = f"采集中 轴={axis} {direction}"
            if angle is not None:
                imu_state += f" 方向盘角度={float(angle):.3f}"
        elif phase == "connecting":
            imu_state = "已连接，等待数据"
        elif phase == "searching":
            imu_state = "搜索中"
        elif phase == "error":
            imu_state = f"错误={snapshot.get('imu_error') or 'unknown'}"
        else:
            imu_state = "空闲"
        self.imu_label.setText(f"IMU：{imu_state}")

        states = snapshot.get("camera_states", [])
        self.camera1_label.setText(f"摄像头 1：{self._format_camera_state(states, 0)}")
        self.camera2_label.setText(f"摄像头 2：{self._format_camera_state(states, 1)}")
        self.imu_angles_label.setText(
            f"Angle X: {self._fmt(snapshot.get('imu_raw_angle_x'))} | "
            f"Angle Y: {self._fmt(snapshot.get('imu_raw_angle_y'))} | "
            f"Angle Z: {self._fmt(snapshot.get('imu_raw_angle_z'))}"
        )
        sample_time = "-"
        if snapshot.get("imu_last_timestamp") is not None:
            sample_time = time.strftime("%H:%M:%S", time.localtime(float(snapshot['imu_last_timestamp'])))
        self.imu_extra_label.setText(
            f"方向盘角度：{self._fmt(snapshot.get('imu_angle'))} | "
            f"Gyro Z: {self._fmt(snapshot.get('imu_gyro_z'))} | 样本时间：{sample_time}"
        )

    def _apply_selected_imu_address(self, _index: int) -> None:
        address = self.imu_device_combo.currentData()
        if address:
            self.imu_address.setText(str(address))

    @staticmethod
    def _fmt(value) -> str:
        if value is None:
            return "-"
        return f"{float(value):.3f}"

    @staticmethod
    def _build_viewfinder() -> QCameraViewfinder:
        viewfinder = QCameraViewfinder()
        viewfinder.setMinimumHeight(220)
        viewfinder.setStyleSheet("background-color: #111; border: 1px solid #555;")
        return viewfinder

    @staticmethod
    def _default_camera_indices(cameras: List[dict]) -> List[int]:
        if len(cameras) >= 2:
            return [len(cameras) - 2, len(cameras) - 1]
        if len(cameras) == 1:
            return [0, 0]
        return [0, 0]

    @staticmethod
    def _restore_or_default(combo: QComboBox, previous_value: str, default_camera_index: int) -> None:
        if previous_value:
            previous_index = combo.findData(previous_value)
            if previous_index >= 0:
                combo.setCurrentIndex(previous_index)
                return
        if combo.count() <= 1:
            return
        combo.setCurrentIndex(min(default_camera_index + 1, combo.count() - 1))

    @staticmethod
    def _format_camera_state(camera_states: List[dict], index: int) -> str:
        if index >= len(camera_states):
            return "无数据"
        state = camera_states[index]
        description = state.get("description") or f"摄像头 {index + 1}"
        if state.get("active"):
            return f"{description} 预览中"
        error = state.get("error")
        if error:
            return f"{description} {error}"
        if state.get("connected"):
            return f"{description} 已连接"
        return f"{description} 未连接"
