from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .enums import ClipStatus, RunState, TriageStatus


@dataclass
class RunMeta:
    run_id: str
    created_at: float
    test_date: str
    vehicle_model: str
    vehicle_id: str
    competitor_version: str
    tester: str
    city: str
    route: str
    weather: str
    day_night: str
    test_function: str = "行车-外部路测试"
    imu_zero_offset_deg: float = 0.0
    imu_angle_axis: str = "angle_z"
    imu_angle_inverted: bool = False
    record_screen: bool = True
    camera_count: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunStatus:
    run_id: str
    state: RunState
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    duration_sec: float = 0.0
    issue_count: int = 0
    screen_file: Optional[str] = None
    rtk_file: Optional[str] = None
    imu_file: Optional[str] = None
    last_error: Optional[str] = None
    screen_record_ready: bool = False
    screen_record_rebuild_needed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


@dataclass
class IssueRecord:
    issue_id: str
    run_id: str
    seq_no: int
    issue_time: float
    issue_time_text: str
    latitude: Optional[float]
    longitude: Optional[float]
    road_type: str
    scene_type: str
    problem_tab: str
    problem_type: str
    target_type: str
    ego_action: str
    case_id: str
    comment: str
    clip_start_time: float
    clip_end_time: float
    clip_file: Optional[str]
    issue_info_file: str
    triage: TriageStatus = TriageStatus.UNTRIAGED
    triage_time: Optional[str] = None
    clip_status: ClipStatus = ClipStatus.PENDING
    marking_schema: str = "legacy"
    active_safety_function: str = ""
    active_safety_mode: str = ""
    speed_kph: str = ""
    takeover_result: str = ""
    road_test_result: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["triage"] = self.triage.value
        payload["clip_status"] = self.clip_status.value
        return payload


@dataclass
class RunPaths:
    root: Path
    meta_file: Path
    status_file: Path
    run_note_file: Path
    screen_dir: Path
    screen_segments_dir: Path
    screen_file: Path
    rtk_dir: Path
    rtk_raw_file: Path
    rtk_samples_file: Path
    imu_dir: Path
    imu_raw_file: Path
    imu_samples_file: Path
    issues_dir: Path
    issues_index_file: Path


@dataclass
class SegmentInfo:
    index: int
    path: Path
    start_offset_sec: float
    end_offset_sec: float
