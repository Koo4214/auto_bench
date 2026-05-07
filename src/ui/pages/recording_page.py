from __future__ import annotations

import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.i18n import zh
from src.ui.widgets.issue_editor import IssueEditorWidget
from src.ui.widgets.steering_wheel_widget import SteeringWheelWidget
from src.ui.widgets.time_series_chart import TimeSeriesChart


class RecordingPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(4)
        root.addWidget(self.main_splitter)

        self.left_panel = self._build_left_panel()
        self.middle_panel = self._build_middle_panel()
        self.right_panel = self._build_right_panel()

        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.middle_panel)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setStretchFactor(2, 4)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_default_sizes)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.issue_editor = IssueEditorWidget()
        self.issue_scroll = QScrollArea()
        self.issue_scroll.setWidgetResizable(True)
        self.issue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.issue_scroll.setFrameShape(QScrollArea.NoFrame)
        self.issue_scroll.setWidget(self.issue_editor)
        layout.addWidget(self.issue_scroll)
        return panel

    def _build_middle_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)

        title = QLabel("实时摘要")
        layout.addWidget(title)

        self.run_label = QLabel("Run: -")
        self.runtime_label = QLabel("时长: 00:00:00")
        self.rtk_label = QLabel("RTK: -")
        self.imu_label = QLabel("IMU: -")
        self.screen_label = QLabel("时间戳: -")
        for label in [
            self.run_label,
            self.runtime_label,
            self.rtk_label,
            self.imu_label,
            self.screen_label,
        ]:
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setWordWrap(False)
            layout.addWidget(label)

        self.steering_chart = SteeringWheelWidget()
        self.steering_angle_chart = TimeSeriesChart("方向盘角度", "#5cadff", " °", window_seconds=6.0, baseline_value=0.0, symmetric_baseline=True, decimals=1)
        self.speed_chart = TimeSeriesChart("车速", "#55d6a9", " m/s", window_seconds=6.0, baseline_value=0.0, decimals=1)
        self.lateral_acc_chart = TimeSeriesChart("横向加速度", "#f7b955", " m/s^2", window_seconds=6.0, baseline_value=0.0, symmetric_baseline=True, decimals=2)
        self.longitudinal_acc_chart = TimeSeriesChart("纵向加速度", "#ff7f7f", " m/s^2", window_seconds=6.0, baseline_value=0.0, symmetric_baseline=True, decimals=2)
        self.jerk_chart = TimeSeriesChart("冲击度", "#b58cff", " m/s^3", window_seconds=6.0, baseline_value=0.0, symmetric_baseline=True, decimals=2)
        for chart in [
            self.steering_chart,
            self.steering_angle_chart,
            self.speed_chart,
            self.lateral_acc_chart,
            self.longitudinal_acc_chart,
            self.jerk_chart,
        ]:
            chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(chart, 1)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(68)
        layout.addWidget(self.log_output)

        self.stop_btn = QPushButton("结束测试")
        layout.addWidget(self.stop_btn)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("双相机预览"))

        self.camera_view_1 = self._build_viewfinder()
        self.camera_view_2 = self._build_viewfinder()
        layout.addWidget(self.camera_view_1, 1)
        layout.addWidget(self.camera_view_2, 1)
        return panel

    def _apply_default_sizes(self) -> None:
        total = self.main_splitter.width()
        if total <= 0:
            return
        left = int(total * 0.4)
        middle = int(total * 0.2)
        right = max(total - left - middle, 0)
        self.main_splitter.setSizes([left, middle, right])

    def append_log(self, message: str) -> None:
        self.log_output.append(message)

    def apply_snapshot(self, snapshot: dict) -> None:
        self.run_label.setText(f"Run: {snapshot.get('run_id') or '-'}")

        rtk_state = zh("connected") if snapshot.get("rtk_connected") else zh("disconnected")
        if snapshot.get("rtk_source"):
            rtk_state += f" [{zh(snapshot['rtk_source'])}]"
        if snapshot.get("rtk_error"):
            rtk_state += f" 错误={snapshot['rtk_error']}"
        self.rtk_label.setText(f"RTK: {rtk_state}")

        imu_phase = snapshot.get("imu_phase")
        imu_source = snapshot.get("imu_source") or "live"
        if imu_phase == "streaming":
            imu_state = f"采集中 [{zh(imu_source)}]"
        elif imu_phase == "connecting":
            imu_state = "已连接，等待数据"
        elif imu_phase == "searching":
            imu_state = "搜索中"
        elif imu_phase == "error":
            imu_state = f"错误={snapshot.get('imu_error') or 'unknown'}"
        else:
            imu_state = "空闲"
        self.imu_label.setText(f"IMU: {imu_state}")

        current_timestamp = snapshot.get("rtk_last_timestamp") or snapshot.get("imu_last_timestamp") or snapshot.get("chart_timestamp")
        if current_timestamp is None:
            timestamp_text = "-"
        else:
            timestamp_text = time.strftime("%H:%M:%S", time.localtime(float(current_timestamp)))
        self.screen_label.setText(f"时间戳: {timestamp_text}")
        self.issue_editor.set_issue_count(snapshot.get("issue_count", 0))

        chart_ts = snapshot.get("chart_timestamp")
        if chart_ts is not None:
            chart_ts = float(chart_ts)
            self.steering_chart.add_sample(chart_ts, snapshot.get("chart_steering"))
            self.steering_angle_chart.add_sample(chart_ts, snapshot.get("chart_steering"))
            self.speed_chart.add_sample(chart_ts, snapshot.get("chart_speed"))
            self.lateral_acc_chart.add_sample(chart_ts, snapshot.get("chart_lateral_acc"))
            self.longitudinal_acc_chart.add_sample(chart_ts, snapshot.get("chart_longitudinal_acc"))
            self.jerk_chart.add_sample(chart_ts, snapshot.get("chart_jerk"))

    def set_runtime(self, seconds: float) -> None:
        seconds = max(0, int(seconds))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        self.runtime_label.setText(f"时长: {hours:02d}:{minutes:02d}:{secs:02d}")

    def clear_charts(self) -> None:
        for chart in [
            self.steering_chart,
            self.steering_angle_chart,
            self.speed_chart,
            self.lateral_acc_chart,
            self.longitudinal_acc_chart,
            self.jerk_chart,
        ]:
            chart.clear()

    @staticmethod
    def _build_viewfinder() -> QCameraViewfinder:
        viewfinder = QCameraViewfinder()
        viewfinder.setMinimumHeight(220)
        viewfinder.setStyleSheet("background-color: #111; border: 1px solid #555;")
        return viewfinder

