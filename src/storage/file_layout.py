from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.domain.models import RunPaths


def build_run_paths(
    base_dir: Path,
    test_date: str,
    vehicle_model: str,
    vehicle_id: str,
    run_id: str,
) -> RunPaths:
    date_dir = base_dir / test_date
    vehicle_dir = date_dir / f"{vehicle_model}_{vehicle_id}"
    run_root = vehicle_dir / run_id
    screen_dir = run_root / "screen"
    segments_dir = screen_dir / "segments"
    rtk_dir = run_root / "rtk"
    imu_dir = run_root / "imu"
    issues_dir = run_root / "issues"
    return RunPaths(
        root=run_root,
        meta_file=run_root / "meta.json",
        status_file=run_root / "status.json",
        run_note_file=run_root / "run_note.txt",
        screen_dir=screen_dir,
        screen_segments_dir=segments_dir,
        screen_file=screen_dir / "screen_record.mp4",
        rtk_dir=rtk_dir,
        rtk_raw_file=rtk_dir / "rtk_raw.txt",
        rtk_samples_file=rtk_dir / "rtk_samples.csv",
        imu_dir=imu_dir,
        imu_raw_file=imu_dir / "imu_raw.json",
        imu_samples_file=imu_dir / "imu_samples.csv",
        issues_dir=issues_dir,
        issues_index_file=issues_dir / "issues.json",
    )


def ensure_run_directories(paths: RunPaths) -> None:
    directories = [
        paths.root,
        paths.screen_dir,
        paths.screen_segments_dir,
        paths.rtk_dir,
        paths.imu_dir,
        paths.issues_dir,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def format_issue_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
