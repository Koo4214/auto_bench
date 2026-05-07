from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List

from PyQt5.QtCore import QTimer
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.run_session_service import RunSessionService


class ProbeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("????????")
        self.resize(1360, 900)
        self.service = RunSessionService(Path.cwd() / "data")
        self.current_run_started = False

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout()
        central.setLayout(root_layout)

        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        root_layout.addWidget(left_panel, 3)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        root_layout.addWidget(right_panel, 2)

        form_layout = QFormLayout()
        self.test_date = QLineEdit("2026-03-12")
        self.vehicle_model = QLineEdit("ProbeVehicle")
        self.vehicle_id = QLineEdit("TEST001")
        self.version = QLineEdit("unknown")
        self.tester = QLineEdit("operator")
        self.city = QLineEdit("Shanghai")
        self.route = QLineEdit("M0")
        self.weather = QLineEdit("Sunny")
        self.day_night = QLineEdit("Day")
        self.rtk_serial_port = QComboBox()
        self.rtk_baudrate = QLineEdit("230400")
        self.imu_address = QLineEdit("E6:FA:D0:DD:6B:D4")
        self.imu_axis_select = QComboBox()
        self.imu_axis_select.addItems(["X", "Y", "Z"])
        self.imu_axis_select.setCurrentText("Z")
        self.imu_invert_select = QComboBox()
        self.imu_invert_select.addItems(["Normal", "Inverted"])
        self.camera1_select = QComboBox()
        self.camera2_select = QComboBox()
        self.refresh_serials_btn = QPushButton("Refresh serial ports")
        self.refresh_cameras_btn = QPushButton("Refresh cameras")

        fields = [
            ("Test date", self.test_date),
            ("Vehicle model", self.vehicle_model),
            ("Plate / ID", self.vehicle_id),
            ("Competitor version", self.version),
            ("Tester", self.tester),
            ("City", self.city),
            ("Route", self.route),
            ("Weather", self.weather),
            ("Day/Night", self.day_night),
            ("RTK serial port", self.rtk_serial_port),
            ("RTK baudrate", self.rtk_baudrate),
            ("IMU BLE address (optional)", self.imu_address),
            ("IMU steering axis", self.imu_axis_select),
            ("Direction", self.imu_invert_select),
            ("Camera 1", self.camera1_select),
            ("Camera 2", self.camera2_select),
        ]
        for label, field in fields:
            form_layout.addRow(label, field)
        serial_button_row = QHBoxLayout()
        serial_button_row.setContentsMargins(0, 0, 0, 0)
        serial_button_row.addWidget(self.refresh_serials_btn)
        serial_widget = QWidget()
        serial_widget.setLayout(serial_button_row)
        form_layout.addRow("", serial_widget)
        form_layout.addRow("", self.refresh_cameras_btn)
        left_layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        self.create_btn = QPushButton("Create run")
        self.self_check_btn = QPushButton("Run self-check")
        self.preview_btn = QPushButton("Start preview")
        self.preview_stop_btn = QPushButton("Stop preview")
        self.rtk_start_btn = QPushButton("Start RTK")
        self.rtk_stop_btn = QPushButton("Stop RTK")
        self.imu_start_btn = QPushButton("Start IMU")
        self.imu_stop_btn = QPushButton("Stop IMU")
        self.start_btn = QPushButton("Start probe")
        self.zero_btn = QPushButton("Set IMU zero")
        self.issue_btn = QPushButton("Mark issue")
        self.stop_btn = QPushButton("Stop probe")
        for button in [
            self.create_btn,
            self.self_check_btn,
            self.preview_btn,
            self.preview_stop_btn,
            self.rtk_start_btn,
            self.rtk_stop_btn,
            self.imu_start_btn,
            self.imu_stop_btn,
            self.start_btn,
            self.zero_btn,
            self.issue_btn,
            self.stop_btn,
        ]:
            button_row.addWidget(button)
        left_layout.addLayout(button_row)

        status_grid = QGridLayout()
        self.status_label = QLabel("State: idle")
        self.run_label = QLabel("Current run: -")
        self.issue_label = QLabel("Issue count: 0")
        self.self_check_label = QLabel("Self-check: not run")
        self.self_check_detail = QLabel("Checks: n/a")
        self.self_check_detail.setWordWrap(True)
        self.rtk_label = QLabel("RTK: idle")
        self.imu_label = QLabel("IMU: idle")
        self.screen_label = QLabel("Screen: idle")
        self.rtk_live_label = QLabel("RTK live: no data")
        self.camera1_label = QLabel("Camera 1: idle")
        self.camera2_label = QLabel("Camera 2: idle")
        self.imu_live_label = QLabel("IMU live: no data")
        self.imu_angle_label = QLabel("Angle X: - | Angle Y: - | Angle Z: -")
        self.imu_gyro_label = QLabel("Steering: - | Gyro Z: - | Sample time: -")

        status_grid.addWidget(self.status_label, 0, 0)
        status_grid.addWidget(self.run_label, 0, 1)
        status_grid.addWidget(self.issue_label, 0, 2)
        status_grid.addWidget(self.self_check_label, 1, 0)
        status_grid.addWidget(self.self_check_detail, 1, 1, 1, 2)
        status_grid.addWidget(self.rtk_label, 2, 0)
        status_grid.addWidget(self.imu_label, 2, 1)
        status_grid.addWidget(self.screen_label, 2, 2)
        status_grid.addWidget(self.rtk_live_label, 3, 0, 1, 3)
        status_grid.addWidget(self.camera1_label, 4, 0, 1, 2)
        status_grid.addWidget(self.camera2_label, 4, 2)
        status_grid.addWidget(self.imu_live_label, 5, 0, 1, 3)
        status_grid.addWidget(self.imu_angle_label, 6, 0, 1, 3)
        status_grid.addWidget(self.imu_gyro_label, 7, 0, 1, 3)
        left_layout.addLayout(status_grid)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output)

        preview_title = QLabel("?????")
        right_layout.addWidget(preview_title)

        self.camera_view_1 = self._build_viewfinder()
        self.camera_view_2 = self._build_viewfinder()
        right_layout.addWidget(self.camera_view_1, 1)
        right_layout.addWidget(self.camera_view_2, 1)
        self.service.bind_camera_viewfinders([self.camera_view_1, self.camera_view_2])

        self.create_btn.clicked.connect(self.create_run)
        self.self_check_btn.clicked.connect(self.run_self_check)
        self.refresh_serials_btn.clicked.connect(self.refresh_serial_options)
        self.preview_btn.clicked.connect(self.start_preview)
        self.preview_stop_btn.clicked.connect(self.stop_preview)
        self.rtk_start_btn.clicked.connect(self.start_rtk_preview)
        self.rtk_stop_btn.clicked.connect(self.stop_rtk_preview)
        self.imu_start_btn.clicked.connect(self.start_imu_preview)
        self.imu_stop_btn.clicked.connect(self.stop_imu_preview)
        self.start_btn.clicked.connect(self.start_probe)
        self.zero_btn.clicked.connect(self.set_imu_zero)
        self.issue_btn.clicked.connect(self.add_issue)
        self.stop_btn.clicked.connect(self.stop_probe)
        self.refresh_cameras_btn.clicked.connect(self.refresh_camera_options)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start()

        self.refresh_serial_options()
        self.refresh_camera_options()
        self.refresh_status()

    def collect_form(self) -> dict:
        return {
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

    def create_run(self) -> None:
        paths = self.service.create_run(self.collect_form())
        self.log(f"Run directory created: {paths.root}")
        self.refresh_status()

    def run_self_check(self) -> None:
        report = self.service.get_preflight_report(
            camera_devices=self._selected_camera_devices(),
            require_rtk=False,
        )
        self._apply_self_check_report(report)
        summary = {
            "pass": "passed",
            "warn": "passed with warnings",
            "fail": "failed",
        }[report["overall"]]
        self.log(f"Self-check result: {summary}")
        for item in report["checks"]:
            icon = {"pass": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}[item["level"]]
            self.log(f"{icon} {item['label']} - {item['message']}")

    def start_preview(self) -> None:
        selected_cameras = self._selected_camera_devices()
        if len(selected_cameras) != 2:
            self.log("Please choose one device for Camera 1 and Camera 2.")
            return
        if len(set(selected_cameras)) != len(selected_cameras):
            self.log("Camera selection is invalid: Camera 1 and Camera 2 must be different devices.")
            return
        self.service.start_camera_preview(camera_devices=selected_cameras)
        self.log("????????")
        self.refresh_status()

    def stop_preview(self) -> None:
        self.service.stop_camera_preview()
        self.log("????????")
        self.refresh_status()

    def start_rtk_preview(self) -> None:
        serial_port = self._rtk_serial_port_value()
        baudrate = self._rtk_serial_baudrate_value()
        self.service.start_rtk_preview(serial_port=serial_port, serial_baudrate=baudrate)
        self.log(f"RTK preview started: {serial_port} @ {baudrate}")
        self.refresh_status()

    def stop_rtk_preview(self) -> None:
        self.service.stop_rtk_preview()
        self.log("RTK preview stopped.")
        self.refresh_status()

    def start_imu_preview(self) -> None:
        imu_address = self.imu_address.text().strip() or None
        imu_axis = self.imu_axis_select.currentText()
        imu_inverted = self.imu_invert_select.currentText() == "Inverted"
        self.service.start_imu_preview(
            imu_address=imu_address,
            imu_axis=imu_axis,
            imu_inverted=imu_inverted,
        )
        self.log(
            f"IMU preview started: {imu_address or 'auto-discovery'} "
            f"axis={imu_axis} inverted={imu_inverted}"
        )
        self.refresh_status()

    def stop_imu_preview(self) -> None:
        self.service.stop_imu_preview()
        self.log("IMU preview stopped.")
        self.refresh_status()

    def start_probe(self) -> None:
        if self.current_run_started:
            self.log("Probe is already running.")
            return
        report = self.service.get_preflight_report(
            camera_devices=self._selected_camera_devices(),
            require_rtk=False,
        )
        self._apply_self_check_report(report)
        if report["overall"] == "fail":
            self.log("Probe start blocked: self-check did not pass.")
            return

        self.service.start_recording(
            serial_port=self._rtk_serial_port_value(),
            serial_baudrate=self._rtk_serial_baudrate_value(),
            imu_address=self.imu_address.text().strip() or None,
            camera_devices=self._selected_camera_devices(),
            imu_axis=self.imu_axis_select.currentText(),
            imu_inverted=self.imu_invert_select.currentText() == "Inverted",
        )
        self.current_run_started = True
        if report["warnings"]:
            self.log("Probe started in degraded mode. Please review self-check warnings.")
        else:
            self.log("Probe started: screen, RTK, IMU, and dual cameras are running.")
        self.refresh_status()

    def add_issue(self) -> None:
        issue = self.service.create_probe_issue()
        self.log(f"Issue created: {issue.issue_id}")
        self.refresh_status()

    def set_imu_zero(self) -> None:
        zero = self.service.set_imu_zero()
        if zero is None:
            self.log("IMU zero failed: no valid IMU sample is available.")
        else:
            self.log(
                f"IMU zero set: axis={self.imu_axis_select.currentText()} "
                f"inverted={self.imu_invert_select.currentText() == 'Inverted'} value={zero:.3f}"
            )
        self.refresh_status()

    def stop_probe(self) -> None:
        if not self.current_run_started:
            self.log("There is no active probe run.")
            return
        self.service.stop_recording(aborted=False)
        self.current_run_started = False
        self.log("Probe stopped: screen stitching and issue clips were processed.")
        self.refresh_status()

    def refresh_status(self) -> None:
        snapshot = self.service.get_probe_snapshot()
        self.status_label.setText(f"State: {snapshot['run_state']}")
        self.run_label.setText(f"Current run: {snapshot['run_id'] or '-'}")
        self.issue_label.setText(f"Issue count: {snapshot['issue_count']}")

        rtk_state = "connected" if snapshot["rtk_connected"] else "disconnected"
        if snapshot["rtk_last_speed"] is not None:
            rtk_state += f" speed={self._fmt(snapshot['rtk_last_speed'])}"
        if snapshot["rtk_error"]:
            rtk_state += f" error={snapshot['rtk_error']}"
        self.rtk_label.setText(f"RTK: {rtk_state}")
        self.rtk_live_label.setText(self._format_rtk_live(snapshot))
        self.imu_label.setText(f"IMU: {self._format_imu_status(snapshot)}")

        screen_state = "stitched" if snapshot["screen_record_ready"] else "segments only / pending"
        self.screen_label.setText(f"Screen: {screen_state}")
        camera_states = snapshot.get("camera_states", [])
        self.camera1_label.setText(f"Camera 1: {self._format_camera_state(camera_states, 0)}")
        self.camera2_label.setText(f"Camera 2: {self._format_camera_state(camera_states, 1)}")
        self._refresh_imu_live(snapshot)

    def log(self, message: str) -> None:
        self.log_output.append(message)

    def refresh_serial_options(self) -> None:
        ports = self.service.list_available_serial_ports()
        previous = self.rtk_serial_port.currentData() or self.rtk_serial_port.currentText()
        self.rtk_serial_port.clear()
        if not ports:
            self.rtk_serial_port.addItem("No serial ports", "")
        else:
            for port in ports:
                self.rtk_serial_port.addItem(port, port)
            if previous:
                index = self.rtk_serial_port.findData(previous)
                if index >= 0:
                    self.rtk_serial_port.setCurrentIndex(index)
                else:
                    default_index = self.rtk_serial_port.findData("COM3")
                    self.rtk_serial_port.setCurrentIndex(default_index if default_index >= 0 else 0)
            else:
                default_index = self.rtk_serial_port.findData("COM3")
                self.rtk_serial_port.setCurrentIndex(default_index if default_index >= 0 else 0)
        self.log(f"Serial ports refreshed: {len(ports)} found.")

    def refresh_camera_options(self) -> None:
        cameras = self.service.list_available_cameras()
        selected_before = [
            self.camera1_select.currentData(),
            self.camera2_select.currentData(),
        ]
        for combo in (self.camera1_select, self.camera2_select):
            combo.clear()
            combo.addItem("Select", "")
        for camera in cameras:
            label = f"{camera['description']} | {camera['device_name']}"
            self.camera1_select.addItem(label, camera["device_name"])
            self.camera2_select.addItem(label, camera["device_name"])
        default_indices = self._default_camera_indices(cameras)
        self._restore_or_default(self.camera1_select, selected_before[0], default_indices[0])
        self._restore_or_default(self.camera2_select, selected_before[1], default_indices[1])
        self.log(f"Camera list refreshed: {len(cameras)} devices found.")

    def _selected_camera_devices(self) -> List[str]:
        selected = [self.camera1_select.currentData(), self.camera2_select.currentData()]
        return [device for device in selected if device]

    def _rtk_serial_port_value(self) -> str:
        value = self.rtk_serial_port.currentData()
        if value:
            return value
        text = self.rtk_serial_port.currentText().strip()
        if text and text != "No serial ports":
            return text
        return "COM3"

    def _rtk_serial_baudrate_value(self) -> int:
        try:
            return int(self.rtk_baudrate.text().strip() or "230400")
        except ValueError:
            return 230400

    def _apply_self_check_report(self, report: dict) -> None:
        level_to_text = {
            "pass": "passed",
            "warn": "warning",
            "fail": "failed",
        }
        self.self_check_label.setText(f"Self-check: {level_to_text[report['overall']]}")
        detail = " | ".join(
            f"{item['label']}={level_to_text[item['level']]}" for item in report["checks"]
        )
        self.self_check_detail.setText(f"Checks: {detail}")

    def _refresh_imu_live(self, snapshot: dict) -> None:
        phase = snapshot.get("imu_phase")
        if phase == "streaming":
            self.imu_live_label.setText("IMU live: streaming")
        elif phase == "connecting":
            self.imu_live_label.setText("IMU live: connected, waiting for samples")
        elif phase == "searching":
            self.imu_live_label.setText("IMU live: searching")
        elif phase == "error":
            self.imu_live_label.setText("IMU live: failed")
        else:
            self.imu_live_label.setText("IMU live: no data")

        angle_x = snapshot.get("imu_raw_angle_x")
        angle_y = snapshot.get("imu_raw_angle_y")
        angle_z = snapshot.get("imu_raw_angle_z")
        steering = snapshot.get("imu_angle")
        gyro_z = snapshot.get("imu_gyro_z")
        timestamp = snapshot.get("imu_last_timestamp")
        self.imu_angle_label.setText(
            f"Angle X: {self._fmt(angle_x)} | Angle Y: {self._fmt(angle_y)} | Angle Z: {self._fmt(angle_z)}"
        )
        time_text = "-"
        if timestamp is not None:
            time_text = time.strftime("%H:%M:%S", time.localtime(float(timestamp)))
        self.imu_gyro_label.setText(
            f"Steering: {self._fmt(steering)} | Gyro Z: {self._fmt(gyro_z)} | Sample time: {time_text}"
        )

    @staticmethod
    def _format_rtk_live(snapshot: dict) -> str:
        if not snapshot.get("rtk_connected"):
            error = snapshot.get("rtk_error")
            return f"RTK live: disconnected ({error})" if error else "RTK live: disconnected"
        latitude = snapshot.get("rtk_last_latitude")
        longitude = snapshot.get("rtk_last_longitude")
        speed = snapshot.get("rtk_last_speed")
        heading = snapshot.get("rtk_last_heading")
        status = snapshot.get("rtk_last_status")
        return (
            f"RTK live: Lat={ProbeWindow._fmt(latitude)} Lon={ProbeWindow._fmt(longitude)} "
            f"V={ProbeWindow._fmt(speed)} Heading={ProbeWindow._fmt(heading)} "
            f"Status={status if status is not None else '-'}"
        )

    @staticmethod
    def _format_imu_status(snapshot: dict) -> str:
        phase = snapshot.get("imu_phase")
        error = snapshot.get("imu_error")
        angle = snapshot.get("imu_angle")
        axis = snapshot.get("imu_axis", "Z")
        inverted = snapshot.get("imu_inverted", False)
        direction = "Inverted" if inverted else "Normal"
        if phase == "streaming":
            if angle is not None:
                return f"streaming axis={axis} {direction} steering={float(angle):.3f}"
            return f"streaming axis={axis} {direction}"
        if phase == "connecting":
            return "connected, waiting for samples"
        if phase == "searching":
            return "searching"
        if phase == "error":
            return f"error={error}" if error else "failed"
        return "disconnected"

    @staticmethod
    def _fmt(value) -> str:
        if value is None:
            return "-"
        return f"{float(value):.3f}"

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
    def _build_viewfinder() -> QCameraViewfinder:
        viewfinder = QCameraViewfinder()
        viewfinder.setMinimumHeight(260)
        viewfinder.setStyleSheet("background-color: #111; border: 1px solid #555;")
        return viewfinder

    @staticmethod
    def _format_camera_state(camera_states: List[dict], index: int) -> str:
        if index >= len(camera_states):
            return "no data"
        state = camera_states[index]
        description = state.get("description") or f"Camera{index + 1}"
        if state.get("active"):
            return f"{description} previewing"
        error = state.get("error")
        if error:
            return f"{description} {error}"
        if state.get("connected"):
            return f"{description} connected"
        return f"{description} disconnected"


def main() -> int:
    app = QApplication(sys.argv)
    window = ProbeWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
