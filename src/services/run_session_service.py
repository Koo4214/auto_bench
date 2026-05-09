from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Dict, Optional, Sequence


from src.domain.enums import RunState
from src.domain.models import RunMeta, RunPaths, RunStatus
from src.domain.test_functions import DEFAULT_TEST_FUNCTION, normalize_test_function
from src.devices.camera_preview import CameraPreviewManager
from src.devices.historical_replay import HistoricalImuReplayDriver, HistoricalRtkReplayDriver
from src.devices.imu_ble_driver import ImuBleDriver
from src.devices.rtk_serial_driver import RtkSerialDriver, list_available_serial_ports
from src.devices.screen_recorder import ScreenSegmentRecorder
from src.app.runtime_tools import resolve_ffmpeg_path
from src.services.clip_service import ClipService
from src.services.issue_service import IssueService
from src.storage.file_layout import build_run_paths, ensure_run_directories
from src.storage.repositories import RunRepository


class RunSessionService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.preview_dir = base_dir.parent / "tmp" / "imu_preview"
        self.rtk_preview_dir = base_dir.parent / "tmp" / "rtk_preview"
        self.repository = RunRepository()
        self.paths: Optional[RunPaths] = None
        self.meta: Optional[RunMeta] = None
        self.status: Optional[RunStatus] = None
        self.screen_recorder: Optional[ScreenSegmentRecorder] = None
        self.issue_service: Optional[IssueService] = None
        self.clip_service = ClipService()
        self.rtk_driver: Optional[object] = None
        self.imu_driver: Optional[ImuBleDriver] = None
        self.camera_manager = CameraPreviewManager(camera_count=2)
        self._last_chart_rtk_timestamp: Optional[float] = None
        self._last_chart_longitudinal_acc: Optional[float] = None
        self._last_chart_jerk: Optional[float] = None

    def bind_camera_viewfinders(self, viewfinders) -> None:
        self.camera_manager.bind_viewfinders(viewfinders)

    def list_available_cameras(self):
        return self.camera_manager.list_available_cameras()

    def start_camera_preview(self, camera_devices: Optional[Sequence[str]] = None) -> None:
        self.camera_manager.start(selected_devices=camera_devices)

    def stop_camera_preview(self) -> None:
        self.camera_manager.stop()

    def list_available_serial_ports(self):
        return list_available_serial_ports()

    def start_rtk_preview(self, serial_port: str = "COM3", serial_baudrate: int = 230400) -> None:
        self.stop_rtk_preview()
        self.rtk_preview_dir.mkdir(parents=True, exist_ok=True)
        self.rtk_driver = RtkSerialDriver(
            raw_file=self.rtk_preview_dir / "rtk_raw.txt",
            samples_file=self.rtk_preview_dir / "rtk_samples.csv",
            serial_port=serial_port,
            baudrate=serial_baudrate,
        )
        self.rtk_driver.start()

    def stop_rtk_preview(self) -> None:
        if self.rtk_driver:
            self.rtk_driver.stop()
            self.rtk_driver = None

    def start_imu_preview(
        self,
        imu_address: Optional[str] = None,
        imu_axis: str = "Z",
        imu_inverted: bool = False,
    ) -> None:
        self.stop_imu_preview()
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        self.imu_driver = ImuBleDriver(
            raw_file=self.preview_dir / "imu_raw.json",
            samples_file=self.preview_dir / "imu_samples.csv",
            preferred_address=imu_address or None,
            steering_axis=imu_axis,
            steering_inverted=imu_inverted,
        )
        self.imu_driver.start()

    def stop_imu_preview(self) -> None:
        if self.imu_driver:
            self.imu_driver.stop()
            self.imu_driver = None

    def create_run(self, form_data: Dict[str, str]) -> RunPaths:
        vehicle_model = form_data["vehicle_model"]
        vehicle_id = form_data["vehicle_id"]
        run_id = time.strftime(f"%m%d%y_{vehicle_model}_{vehicle_id}_Run%Y%m%d_%H%M%S", time.localtime())
        created_at = time.time()
        self.meta = RunMeta(
            run_id=run_id,
            created_at=created_at,
            test_date=form_data["test_date"],
            vehicle_model=vehicle_model,
            vehicle_id=vehicle_id,
            competitor_version=form_data["competitor_version"],
            tester=form_data["tester"],
            city=form_data["city"],
            route=form_data["route"],
            weather=form_data["weather"],
            day_night=form_data["day_night"],
            test_function=normalize_test_function(form_data.get("test_function", DEFAULT_TEST_FUNCTION)),
        )
        self.paths = build_run_paths(
            self.base_dir,
            self.meta.test_date,
            self.meta.vehicle_model,
            self.meta.vehicle_id,
            self.meta.run_id,
        )
        ensure_run_directories(self.paths)
        self.status = RunStatus(
            run_id=run_id,
            state=RunState.PREPARING,
            screen_file=str(self.paths.screen_file),
            rtk_file=str(self.paths.rtk_samples_file),
            imu_file=str(self.paths.imu_samples_file),
            screen_record_rebuild_needed=False,
            screen_record_ready=False,
        )
        self.issue_service = IssueService(self.paths, run_id)
        self.repository.save_meta(self.paths.meta_file, self.meta)
        self.repository.save_status(self.paths.status_file, self.status)
        self.paths.run_note_file.write_text("", encoding="utf-8")
        return self.paths

    def start_recording(
        self,
        width: int = 1920,
        height: int = 1080,
        serial_port: str = "COM3",
        serial_baudrate: int = 230400,
        imu_address: Optional[str] = None,
        camera_devices: Optional[Sequence[str]] = None,
        imu_axis: str = "Z",
        imu_inverted: bool = False,
        sample_replay_dir: Optional[Path] = None,
    ) -> None:
        if not self.paths or not self.status or not self.meta:
            raise RuntimeError("run not created")

        replay_dir = self._resolve_sample_replay_dir(sample_replay_dir)
        replay_imu_available = bool(replay_dir and HistoricalImuReplayDriver.has_source(replay_dir))
        existing_imu_driver = self.imu_driver
        reuse_live_imu = bool(
            not replay_imu_available
            and existing_imu_driver is not None
            and existing_imu_driver.connected
            and existing_imu_driver.phase in ('connecting', 'streaming')
            and existing_imu_driver.matches_config(imu_address or None, imu_axis, imu_inverted)
        )
        if not reuse_live_imu:
            self.stop_imu_preview()
        self.stop_rtk_preview()
        self.screen_recorder = ScreenSegmentRecorder(
            segments_dir=self.paths.screen_segments_dir,
            width=width,
            height=height,
        )
        self.rtk_driver = self._build_rtk_driver(replay_dir, serial_port, serial_baudrate)
        if reuse_live_imu and existing_imu_driver is not None:
            existing_imu_driver.redirect_outputs(self.paths.imu_raw_file, self.paths.imu_samples_file)
            self.imu_driver = existing_imu_driver
        else:
            self.imu_driver = self._build_imu_driver(replay_dir, imu_address, imu_axis, imu_inverted)

        self.screen_recorder.start()
        self.start_camera_preview(camera_devices=camera_devices)
        if self.rtk_driver:
            self.rtk_driver.start()
        if self.imu_driver and not reuse_live_imu:
            self.imu_driver.start()
        self.meta.imu_angle_axis = f"angle_{imu_axis.lower()}"
        self.meta.imu_angle_inverted = imu_inverted
        self.repository.save_meta(self.paths.meta_file, self.meta)
        self._last_chart_rtk_timestamp = None
        self._last_chart_longitudinal_acc = None
        self._last_chart_jerk = None

        self.status = replace(
            self.status,
            state=RunState.RECORDING,
            started_at=time.time(),
            screen_record_ready=False,
            screen_record_rebuild_needed=False,
        )
        self.repository.save_status(self.paths.status_file, self.status)

    def create_probe_issue(
        self,
        road_type: str = "UrbanMainRoad",
        scene_type: str = "Straight",
        problem_tab: str = "NoIssue",
        problem_type: str = "SceneRecord",
        target_type: str = "None",
        ego_action: str = "NoAction",
        case_id: str = "",
        comment: str = "",
        marking_schema: str = "legacy",
        active_safety_function: str = "",
        active_safety_mode: str = "",
        speed_kph: str = "",
        takeover_result: str = "",
        road_test_result: str = "",
        test_result: str = "",
        severity_level: str = "",
        parking_subject_scene: str = "",
        parking_space_category: str = "",
        recognition_result: str = "",
        park_in_result: str = "",
        park_out_result: str = "",
        obstacle_result: str = "",
        pose_result: str = "",
        jerk_result: str = "",
        parking_time_sec: str = "",
        maneuver_count: str = "",
    ):
        if not self.status or not self.issue_service:
            raise RuntimeError("run not started")
        if self.status.state != RunState.RECORDING:
            raise RuntimeError("run must be recording before adding issues")

        issue_time = time.time()
        latitude = None
        longitude = None
        if self.rtk_driver is not None:
            latitude, longitude = self.rtk_driver.get_latest_location()
        issue = self.issue_service.create_issue(
            issue_time=issue_time,
            latitude=latitude,
            longitude=longitude,
            road_type=road_type,
            scene_type=scene_type,
            problem_tab=problem_tab,
            problem_type=problem_type,
            target_type=target_type,
            ego_action=ego_action,
            case_id=case_id,
            comment=comment,
            marking_schema=marking_schema,
            active_safety_function=active_safety_function,
            active_safety_mode=active_safety_mode,
            speed_kph=speed_kph,
            takeover_result=takeover_result,
            road_test_result=road_test_result,
            test_result=test_result,
            severity_level=severity_level,
            parking_subject_scene=parking_subject_scene,
            parking_space_category=parking_space_category,
            recognition_result=recognition_result,
            park_in_result=park_in_result,
            park_out_result=park_out_result,
            obstacle_result=obstacle_result,
            pose_result=pose_result,
            jerk_result=jerk_result,
            parking_time_sec=parking_time_sec,
            maneuver_count=maneuver_count,
        )
        self.status = replace(self.status, issue_count=len(self.issue_service.issues))
        self.repository.save_status(self.paths.status_file, self.status)
        return issue

    def set_imu_zero(self) -> Optional[float]:
        if not self.imu_driver:
            return None
        offset = self.imu_driver.set_zero()
        if offset is not None and self.meta and self.paths:
            self.meta.imu_zero_offset_deg = offset
            self.repository.save_meta(self.paths.meta_file, self.meta)
        return offset

    def stop_recording(self, aborted: bool = False) -> None:
        if not self.paths or not self.status:
            return

        self.status = replace(self.status, state=RunState.STOPPING)
        self.repository.save_status(self.paths.status_file, self.status)

        ended_at = time.time()
        if self.rtk_driver:
            self.rtk_driver.stop()
        if self.imu_driver:
            self.imu_driver.stop()
            self.imu_driver = None
        self.stop_camera_preview()
        if self.screen_recorder:
            self.screen_recorder.stop()

        started_at = self.status.started_at or ended_at
        duration_sec = max(0.0, ended_at - started_at)
        state = RunState.ABORTED if aborted else RunState.COMPLETED
        rebuild_needed = bool(aborted)

        if self.screen_recorder and not aborted:
            try:
                self.screen_recorder.stitch(self.paths.screen_file)
            except Exception as exc:
                rebuild_needed = True
                self.status = replace(self.status, last_error=str(exc))

        self._process_issue_clips(duration_sec)

        self.status = replace(
            self.status,
            state=state,
            ended_at=ended_at,
            duration_sec=duration_sec,
            screen_record_ready=self.paths.screen_file.exists(),
            screen_record_rebuild_needed=rebuild_needed,
        )
        self.repository.save_status(self.paths.status_file, self.status)


    def get_preflight_report(
        self,
        camera_devices: Optional[Sequence[str]] = None,
        require_rtk: bool = False,
        require_run_created: bool = True,
        sample_replay_dir: Optional[Path] = None,
    ) -> Dict[str, object]:
        camera_devices = list(camera_devices or [])
        replay_dir = self._resolve_sample_replay_dir(sample_replay_dir)
        camera_states = self.camera_manager.get_snapshot()
        active_selected = []
        ffmpeg_ready = resolve_ffmpeg_path() is not None
        replay_imu_ready = bool(replay_dir and HistoricalImuReplayDriver.has_source(replay_dir))
        replay_rtk_ready = bool(replay_dir and HistoricalRtkReplayDriver.has_source(replay_dir))
        imu_ready = replay_imu_ready or bool(
            self.imu_driver
            and self.imu_driver.phase == "streaming"
            and self.imu_driver.has_samples
        )

        for device_name in camera_devices:
            matched = next(
                (state for state in camera_states if state.get("device_name") == device_name),
                None,
            )
            if matched and matched.get("active"):
                active_selected.append(device_name)

        run_ready = self.paths is not None if require_run_created else True
        run_message = (
            "Run directory is ready."
            if self.paths is not None
            else ("Run folder will be created when the test starts." if not require_run_created else "Create a run first.")
        )

        checks = [
            {
                "key": "run_created",
                "label": "Run created",
                "level": "pass" if run_ready else "fail",
                "message": run_message,
                "blocking": require_run_created,
            },
            {
                "key": "screen_recorder",
                "label": "Screen recorder",
                "level": "pass" if ffmpeg_ready else "fail",
                "message": "ffmpeg is available." if ffmpeg_ready else "ffmpeg is missing.",
                "blocking": True,
            },
            {
                "key": "camera_selection",
                "label": "Camera selection",
                "level": "pass" if len(camera_devices) == 2 and len(set(camera_devices)) == 2 else "fail",
                "message": "Two different camera devices are selected."
                if len(camera_devices) == 2 and len(set(camera_devices)) == 2
                else "Pick two different camera devices.",
                "blocking": True,
            },
            {
                "key": "camera_preview",
                "label": "Camera preview",
                "level": "pass" if len(active_selected) == 2 else "fail",
                "message": "Both camera previews are active."
                if len(active_selected) == 2
                else "Start preview and confirm both cameras are showing frames.",
                "blocking": True,
            },
            {
                "key": "imu_stream",
                "label": "IMU stream",
                "level": "pass" if imu_ready else "fail",
                "message": "IMU samples are streaming."
                if imu_ready
                else ("Sample IMU replay is ready." if replay_imu_ready else "Start IMU and wait for live samples."),
                "blocking": True,
            },
        ]

        rtk_ok = replay_rtk_ready or (self.rtk_driver is not None and (
            self.rtk_driver.connected or self.rtk_driver.last_sample is not None
        ))
        if require_rtk:
            checks.append(
                {
                    "key": "rtk_stream",
                    "label": "RTK stream",
                    "level": "pass" if rtk_ok else "fail",
                    "message": "RTK is connected and streaming." if rtk_ok else ("Sample RTK replay is ready." if replay_rtk_ready else "RTK is not connected yet."),
                    "blocking": True,
                }
            )
        else:
            checks.append(
                {
                    "key": "rtk_stream",
                    "label": "RTK stream",
                    "level": "pass" if rtk_ok else "warn",
                    "message": "RTK is connected and streaming." if rtk_ok else ("Sample RTK replay is ready." if replay_rtk_ready else "RTK is optional for the current M0 pass."),
                    "blocking": False,
                }
            )

        blocking_failures = [item for item in checks if item["blocking"] and item["level"] != "pass"]
        warnings = [item for item in checks if item["level"] == "warn"]
        overall = "pass" if not blocking_failures and not warnings else ("warn" if not blocking_failures else "fail")
        return {
            "overall": overall,
            "checks": checks,
            "blocking_failures": blocking_failures,
            "warnings": warnings,
        }

    def get_probe_snapshot(self) -> Dict[str, object]:
        imu_sample = self.imu_driver.last_sample if self.imu_driver and self.imu_driver.last_sample else None
        rtk_sample = self.rtk_driver.last_sample if self.rtk_driver and self.rtk_driver.last_sample else None
        meta_axis = "Z"
        if self.meta and self.meta.imu_angle_axis:
            meta_axis = self.meta.imu_angle_axis.split("_")[-1].upper()
        chart_metrics = self._update_chart_metrics(rtk_sample)
        chart_timestamp = None
        if rtk_sample and rtk_sample.get('local_timestamp') is not None:
            chart_timestamp = float(rtk_sample['local_timestamp'])
        elif imu_sample and imu_sample.get('local_timestamp') is not None:
            chart_timestamp = float(imu_sample['local_timestamp'])
        case_id_counts: Dict[str, int] = {}
        if self.issue_service:
            for issue in self.issue_service.issues:
                case_id = issue.case_id.strip()
                if case_id:
                    case_id_counts[case_id] = case_id_counts.get(case_id, 0) + 1
        return {
            "run_state": self.status.state.value if self.status else "idle",
            "run_id": self.status.run_id if self.status else None,
            "issue_count": self.status.issue_count if self.status else 0,
            "case_id_counts": case_id_counts,
            "rtk_connected": self.rtk_driver.connected if self.rtk_driver else False,
            "rtk_source": getattr(self.rtk_driver, 'mode_label', 'live') if self.rtk_driver else None,
            "rtk_last_speed": rtk_sample.get("vehicle_speed") if rtk_sample else None,
            "rtk_last_heading": rtk_sample.get("heading") if rtk_sample else None,
            "rtk_last_latitude": rtk_sample.get("latitude") if rtk_sample else None,
            "rtk_last_longitude": rtk_sample.get("longitude") if rtk_sample else None,
            "rtk_last_status": rtk_sample.get("status") if rtk_sample else None,
            "rtk_last_acc_x": rtk_sample.get('acc_x') if rtk_sample else None,
            "rtk_last_acc_y": rtk_sample.get('acc_y') if rtk_sample else None,
            "rtk_last_timestamp": rtk_sample.get('local_timestamp') if rtk_sample else None,
            "rtk_error": self.rtk_driver.last_error if self.rtk_driver else None,
            "imu_connected": self.imu_driver.connected if self.imu_driver else False,
            "imu_source": getattr(self.imu_driver, 'mode_label', 'live') if self.imu_driver else None,
            "imu_phase": self.imu_driver.phase if self.imu_driver else "idle",
            "imu_axis": self.imu_driver.steering_axis if self.imu_driver else meta_axis,
            "imu_inverted": self.imu_driver.steering_inverted if self.imu_driver else (self.meta.imu_angle_inverted if self.meta else False),
            "imu_has_samples": self.imu_driver.has_samples if self.imu_driver else False,
            "imu_angle": imu_sample.get("steering_angle_deg") if imu_sample else None,
            "imu_raw_angle_x": imu_sample.get("angle_x_deg") if imu_sample else None,
            "imu_raw_angle_y": imu_sample.get("angle_y_deg") if imu_sample else None,
            "imu_raw_angle_z": imu_sample.get("angle_z_deg") if imu_sample else None,
            "imu_gyro_z": imu_sample.get("gyro_z_dps") if imu_sample else None,
            "imu_last_timestamp": imu_sample.get("local_timestamp") if imu_sample else None,
            "imu_error": self.imu_driver.last_error if self.imu_driver else None,
            "chart_timestamp": chart_timestamp,
            "chart_steering": imu_sample.get('steering_angle_deg') if imu_sample else None,
            "chart_speed": rtk_sample.get('vehicle_speed') if rtk_sample else None,
            "chart_lateral_acc": chart_metrics.get('lateral_acc'),
            "chart_longitudinal_acc": chart_metrics.get('longitudinal_acc'),
            "chart_jerk": chart_metrics.get('jerk'),
            "screen_record_ready": self.status.screen_record_ready if self.status else False,
            "camera_states": self.camera_manager.get_snapshot(),
            "available_cameras": self.camera_manager.list_available_cameras(),
        }

    @staticmethod
    def _resolve_sample_replay_dir(sample_replay_dir: Optional[Path]) -> Optional[Path]:
        if sample_replay_dir is None:
            return None
        replay_dir = Path(sample_replay_dir)
        return replay_dir if replay_dir.exists() else None

    def _build_rtk_driver(self, replay_dir: Optional[Path], serial_port: str, serial_baudrate: int):
        if replay_dir and HistoricalRtkReplayDriver.has_source(replay_dir):
            return HistoricalRtkReplayDriver(
                source_dir=replay_dir,
                raw_file=self.paths.rtk_raw_file,
                samples_file=self.paths.rtk_samples_file,
            )
        return RtkSerialDriver(
            raw_file=self.paths.rtk_raw_file,
            samples_file=self.paths.rtk_samples_file,
            serial_port=serial_port,
            baudrate=serial_baudrate,
        )

    def _build_imu_driver(
        self,
        replay_dir: Optional[Path],
        imu_address: Optional[str],
        imu_axis: str,
        imu_inverted: bool,
    ):
        if replay_dir and HistoricalImuReplayDriver.has_source(replay_dir):
            return HistoricalImuReplayDriver(
                source_dir=replay_dir,
                raw_file=self.paths.imu_raw_file,
                samples_file=self.paths.imu_samples_file,
                steering_axis=imu_axis,
                steering_inverted=imu_inverted,
            )
        return ImuBleDriver(
            raw_file=self.paths.imu_raw_file,
            samples_file=self.paths.imu_samples_file,
            preferred_address=imu_address or None,
            steering_axis=imu_axis,
            steering_inverted=imu_inverted,
        )

    def _update_chart_metrics(self, rtk_sample: Optional[Dict[str, object]]) -> Dict[str, Optional[float]]:
        longitudinal_acc = None
        lateral_acc = None
        if rtk_sample is not None:
            longitudinal_acc = rtk_sample.get('acc_x')
            lateral_acc = rtk_sample.get('acc_y')
            timestamp = rtk_sample.get('local_timestamp')
            if timestamp is not None:
                timestamp = float(timestamp)
                if (
                    self._last_chart_rtk_timestamp is not None
                    and self._last_chart_longitudinal_acc is not None
                    and longitudinal_acc is not None
                    and timestamp > self._last_chart_rtk_timestamp
                ):
                    dt = timestamp - self._last_chart_rtk_timestamp
                    if dt > 1e-6:
                        self._last_chart_jerk = (float(longitudinal_acc) - self._last_chart_longitudinal_acc) / dt
                self._last_chart_rtk_timestamp = timestamp
                if longitudinal_acc is not None:
                    self._last_chart_longitudinal_acc = float(longitudinal_acc)
        return {
            'longitudinal_acc': float(longitudinal_acc) if longitudinal_acc is not None else None,
            'lateral_acc': float(lateral_acc) if lateral_acc is not None else None,
            'jerk': self._last_chart_jerk,
        }

    def _process_issue_clips(self, run_duration_sec: float) -> None:
        if not self.screen_recorder or not self.issue_service or not self.status or not self.status.started_at:
            return

        segments = self.screen_recorder.build_segment_manifest(run_duration_sec)
        for issue in self.issue_service.issues:
            clip_output = self.paths.issues_dir / issue.issue_id / "clip.mp4"
            clip_start = max(0.0, issue.clip_start_time - self.status.started_at)
            clip_end = max(0.0, issue.clip_end_time - self.status.started_at)
            clip_end = min(run_duration_sec, clip_end)
            try:
                self.clip_service.create_clip(segments, clip_start, clip_end, clip_output)
                self.issue_service.mark_clip_ready(issue.issue_id, clip_output)
            except Exception:
                self.issue_service.mark_clip_failed(issue.issue_id)
