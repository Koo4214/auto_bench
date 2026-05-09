from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import QTimer, qInstallMessageHandler
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget

from src.services.playback_service import PlaybackService
from src.services.run_session_service import RunSessionService
from src.ui.i18n import zh
from src.ui.pages.calibration_page import CalibrationPage
from src.ui.pages.playback_page import PlaybackPage
from src.ui.pages.recording_page import RecordingPage
from src.ui.pages.run_setup_page import RunSetupPage
from src.ui.widgets.imu_scan_worker import ImuScanWorker


def _qt_message_handler(_msg_type, _context, message):
    if 'Unsupported media type' in message:
        return
    sys.stderr.write(message + '\n')


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("竞品对标工具")
        self.resize(1440, 920)
        self.service = RunSessionService(Path.cwd() / "data")
        self.playback_service = PlaybackService(Path.cwd() / "data")
        self.recording_started_at = None
        self.pending_form = None
        self.pending_output_path = str(Path.cwd() / "data")
        self.imu_scan_worker: Optional[ImuScanWorker] = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.setup_page = RunSetupPage()
        self.calibration_page = CalibrationPage()
        self.recording_page = RecordingPage()
        self.playback_page = PlaybackPage(self.playback_service)
        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.calibration_page)
        self.stack.addWidget(self.recording_page)
        self.stack.addWidget(self.playback_page)

        # 同步配置中的输出路径到 service
        configured_output = self.setup_page.output_path_value()
        if configured_output:
            self.service.base_dir = Path(configured_output)
            self.playback_service.set_base_dir(Path(configured_output))
            self.pending_output_path = configured_output

        self.setup_page.playback_btn.setEnabled(True)
        self.setup_page.next_btn.clicked.connect(self.go_to_calibration)
        self.setup_page.playback_btn.clicked.connect(self.open_playback)
        self.calibration_page.back_btn.clicked.connect(self.back_to_setup)
        self.calibration_page.refresh_serial_action.triggered.connect(self.refresh_serial_options)
        self.calibration_page.refresh_cameras_action.triggered.connect(self.refresh_camera_options)
        self.calibration_page.scan_imu_btn.clicked.connect(self.scan_imu_devices)
        self.calibration_page.sample_replay_browse_btn.clicked.connect(self.calibration_page.browse_sample_replay_dir)
        self.calibration_page.preview_action.triggered.connect(self.start_preview)
        self.calibration_page.preview_stop_action.triggered.connect(self.stop_preview)
        self.calibration_page.imu_start_action.triggered.connect(self.start_imu)
        self.calibration_page.imu_stop_action.triggered.connect(self.stop_imu)
        self.calibration_page.rtk_start_action.triggered.connect(self.start_rtk)
        self.calibration_page.rtk_stop_action.triggered.connect(self.stop_rtk)
        self.calibration_page.imu_zero_action.triggered.connect(self.set_imu_zero)
        self.calibration_page.self_check_btn.clicked.connect(self.run_self_check)
        self.calibration_page.start_test_btn.clicked.connect(self.start_test)
        self.recording_page.issue_editor.add_issue_btn.clicked.connect(self.create_issue)
        self.recording_page.stop_btn.clicked.connect(self.stop_test)
        self.playback_page.back_btn.clicked.connect(self.back_from_playback)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start()

        self.service.bind_camera_viewfinders([
            self.calibration_page.camera_view_1,
            self.calibration_page.camera_view_2,
        ])
        self.refresh_serial_options()
        self.refresh_camera_options()
        self.refresh_status()

    def go_to_calibration(self) -> None:
        # 检查 FFmpeg 路径是否有效
        ffmpeg_path = self.setup_page.ffmpeg_path_value()
        if ffmpeg_path and not Path(ffmpeg_path).exists():
            self._message("配置错误", f"指定的 FFmpeg 路径不存在:\n{ffmpeg_path}")
            return
        # 若未指定路径则尝试自动解析，解析失败则拦截
        if not ffmpeg_path:
            from src.app.runtime_tools import resolve_ffmpeg_path
            auto_path = resolve_ffmpeg_path()
            if not auto_path:
                self._message("配置错误", "未找到 FFmpeg，请在设置页面指定 FFmpeg 路径。")
                return

        self.pending_form = self.setup_page.collect_form()
        self.pending_output_path = self.setup_page.output_path_value()
        self.setup_page.save_config_silent()
        self.setup_page.append_log(f"待使用输出路径：{self.pending_output_path}")
        self.calibration_page.append_log("已采集 run 元数据，请先完成校准再开始测试。")
        self.refresh_serial_options()
        self.stack.setCurrentWidget(self.calibration_page)
        self.refresh_status()

    def open_playback(self) -> None:
        output_path = self.setup_page.output_path_value()
        self.playback_service.set_base_dir(Path(output_path))
        self.playback_page.set_output_path(output_path)
        self.playback_page.refresh_runs()
        self.stack.setCurrentWidget(self.playback_page)

    def back_from_playback(self) -> None:
        self.stack.setCurrentWidget(self.setup_page)

    def back_to_setup(self) -> None:
        self.stop_preview()
        self.stop_imu()
        self.stop_rtk()
        self.stack.setCurrentWidget(self.setup_page)

    def refresh_serial_options(self) -> None:
        ports = self.service.list_available_serial_ports()
        self.calibration_page.set_serial_options(ports)
        self.calibration_page.append_log(f"串口列表已刷新，共发现 {len(ports)} 个串口。")

    def refresh_camera_options(self) -> None:
        cameras = self.service.list_available_cameras()
        self.calibration_page.set_camera_options(cameras)
        self.calibration_page.append_log(f"摄像头列表已刷新，共发现 {len(cameras)} 路设备。")

    def scan_imu_devices(self) -> None:
        if self.imu_scan_worker is not None and self.imu_scan_worker.isRunning():
            return
        self.calibration_page.set_imu_scan_busy(True)
        self.calibration_page.append_log("正在扫描蓝牙 IMU，请稍候...")
        worker = ImuScanWorker(preferred_name_contains="WT", timeout_seconds=8.0)
        worker.scan_finished.connect(self._handle_imu_scan_finished)
        worker.scan_failed.connect(self._handle_imu_scan_failed)
        worker.finished.connect(self._cleanup_imu_scan_worker)
        self.imu_scan_worker = worker
        worker.start()

    def _handle_imu_scan_finished(self, devices: List[dict]) -> None:
        self.calibration_page.set_imu_scan_busy(False)
        self.calibration_page.set_imu_device_options(devices)
        if devices:
            selected = devices[0]
            self.calibration_page.append_log(
                f"扫描到 {len(devices)} 个 WT 系列 IMU，已填入 {selected['address']}。"
            )
        else:
            self.calibration_page.append_log("未扫描到名称包含 WT 的蓝牙 IMU。")

    def _handle_imu_scan_failed(self, message: str) -> None:
        self.calibration_page.set_imu_scan_busy(False)
        self.calibration_page.append_log(f"蓝牙 IMU 扫描失败：{message}")
        self._message("蓝牙 IMU 扫描", f"扫描失败：{message}")

    def _cleanup_imu_scan_worker(self) -> None:
        if self.imu_scan_worker is None:
            return
        self.imu_scan_worker.deleteLater()
        self.imu_scan_worker = None
        self.calibration_page.set_imu_scan_busy(False)

    def start_preview(self) -> None:
        devices = self.calibration_page.selected_camera_devices()
        if len(devices) != 2 or len(set(devices)) != 2:
            self._message("传感器校准", "请先选择两路不同的摄像头设备。")
            return
        self.service.bind_camera_viewfinders([
            self.calibration_page.camera_view_1,
            self.calibration_page.camera_view_2,
        ])
        self.service.start_camera_preview(camera_devices=devices)
        self.calibration_page.append_log("双相机预览已启动。")

    def stop_preview(self) -> None:
        self.service.stop_camera_preview()
        self.calibration_page.append_log("双相机预览已停止。")

    def start_imu(self) -> None:
        self.service.start_imu_preview(
            imu_address=self.calibration_page.imu_address_value(),
            imu_axis=self.calibration_page.imu_axis_value(),
            imu_inverted=self.calibration_page.imu_inverted_value(),
        )
        self.calibration_page.append_log("IMU 预览已启动。")

    def stop_imu(self) -> None:
        self.service.stop_imu_preview()
        self.calibration_page.append_log("IMU 预览已停止。")

    def start_rtk(self) -> None:
        self.service.start_rtk_preview(
            serial_port=self.calibration_page.rtk_serial_port_value(),
            serial_baudrate=self.calibration_page.rtk_serial_baudrate_value(),
        )
        self.calibration_page.append_log(
            f"RTK 预览已启动：{self.calibration_page.rtk_serial_port_value()} @ {self.calibration_page.rtk_serial_baudrate_value()}"
        )

    def stop_rtk(self) -> None:
        self.service.stop_rtk_preview()
        self.calibration_page.append_log("RTK 预览已停止。")

    def set_imu_zero(self) -> None:
        offset = self.service.set_imu_zero()
        if offset is None:
            self._message("传感器校准", "当前还没有有效 IMU 采样，无法设置零点。")
            return
        self.calibration_page.append_log(f"IMU 零点已设置为 {offset:.3f}。")

    def run_self_check(self) -> dict:
        sample_replay_dir = self.calibration_page.sample_replay_dir_value()
        report = self.service.get_preflight_report(
            camera_devices=self.calibration_page.selected_camera_devices(),
            require_rtk=False,
            require_run_created=False,
            sample_replay_dir=Path(sample_replay_dir) if sample_replay_dir else None,
        )
        self.calibration_page.apply_self_check_report(report)
        summary = {
            "pass": "通过",
            "warn": "通过（有警告）",
            "fail": "失败",
        }[report["overall"]]
        self.calibration_page.append_log(f"自检结果：{summary}。")
        for item in report["checks"]:
            icon = {"pass": "[通过]", "warn": "[警告]", "fail": "[失败]"}[item["level"]]
            self.calibration_page.append_log(f"{icon} {item['label']} - {item['message']}")
        return report

    def start_test(self) -> None:
        if self.pending_form is None:
            self._message("传感器校准", "请先在设置页填写 run 信息。")
            return

        report = self.run_self_check()
        if report["overall"] == "fail":
            self._message("传感器校准", "启动测试被拦截，请先修复自检失败项。")
            return

        self.service.base_dir = Path(self.pending_output_path)
        run_form = dict(self.pending_form)
        paths = self.service.create_run(run_form)
        self.recording_page.issue_editor.set_test_function(run_form["test_function"])
        self.calibration_page.append_log(f"已创建 run 目录：{paths.root}")
        self.setup_page.append_log(f"已创建 run 目录：{paths.root}")
        self.calibration_page.append_log(f"测试功能：{run_form['test_function']}")

        self.service.bind_camera_viewfinders([
            self.recording_page.camera_view_1,
            self.recording_page.camera_view_2,
        ])
        sample_replay_dir = self.calibration_page.sample_replay_dir_value()
        self.service.start_recording(
            serial_port=self.calibration_page.rtk_serial_port_value(),
            serial_baudrate=self.calibration_page.rtk_serial_baudrate_value(),
            imu_address=self.calibration_page.imu_address_value(),
            camera_devices=self.calibration_page.selected_camera_devices(),
            imu_axis=self.calibration_page.imu_axis_value(),
            imu_inverted=self.calibration_page.imu_inverted_value(),
            sample_replay_dir=Path(sample_replay_dir) if sample_replay_dir else None,
        )
        self.recording_started_at = time.time()
        self.recording_page.clear_charts()
        if sample_replay_dir:
            self.recording_page.append_log(f"已使用样例回放开始录制：{sample_replay_dir}")
        else:
            self.recording_page.append_log("已开始录制。")
        self.stack.setCurrentWidget(self.recording_page)
        self.refresh_status()

    def create_issue(self) -> None:
        payload = self.recording_page.issue_editor.get_issue_payload()
        issue = self.service.create_probe_issue(**payload)
        self.recording_page.issue_editor.clear_comment()
        self.recording_page.append_log(f"已创建问题打点：{issue.issue_id}")
        self.refresh_status()

    def stop_test(self) -> None:
        # 获取路径信息（stop_recording 前获取，因为 stop 后可能清空）
        run_paths = self.service.paths

        self.service.stop_recording(aborted=False)
        self.recording_page.append_log("已结束录制。")

        # 结束录制后询问是否上传
        if run_paths and run_paths.root.exists():
            reply = QMessageBox.question(
                self,
                "上传数据",
                "测试已结束，是否立刻上传数据到 OSS？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                # 启动 OSS 上传
                try:
                    from src.services.oss_upload_service import OssUploadWorker
                    from src.ui.widgets.upload_progress_dialog import UploadProgressDialog

                    worker = OssUploadWorker(run_paths.root, self.service.base_dir)
                    dialog = UploadProgressDialog(self)
                    dialog.connect_worker(worker)
                    dialog.worker = worker
                    worker.start()
                    dialog.exec_()
                except Exception as exc:
                    print(f"[OSS上传] 启动上传失败: {exc}")

        self.recording_started_at = None
        self.pending_form = None
        self.stack.setCurrentWidget(self.setup_page)
        self.refresh_status()

    def refresh_status(self) -> None:
        snapshot = self.service.get_probe_snapshot()
        self.calibration_page.apply_snapshot(snapshot)
        self.recording_page.apply_snapshot(snapshot)
        if self.recording_started_at is not None:
            self.recording_page.set_runtime(time.time() - self.recording_started_at)
        else:
            self.recording_page.set_runtime(0)
        self.setup_page.status_label.setText(f"状态：{zh(snapshot.get('run_state', 'idle'))}")

    @staticmethod
    def _message(title: str, text: str) -> None:
        QMessageBox.information(None, title, text)


def main() -> int:
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
