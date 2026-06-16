from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import List, Optional

from src.domain.enums import ClipStatus, TriageStatus
from src.domain.models import IssueRecord, RunPaths
from src.storage.file_layout import format_issue_time
from src.storage.repositories import IssueRepository


class IssueService:
    def __init__(self, paths: RunPaths, run_id: str) -> None:
        self.paths = paths
        self.run_id = run_id
        self.repository = IssueRepository()
        self.issues: List[IssueRecord] = []

    def create_issue(
        self,
        issue_time: float,
        latitude: Optional[float],
        longitude: Optional[float],
        road_type: str,
        scene_type: str,
        problem_tab: str,
        problem_type: str,
        target_type: str,
        ego_action: str,
        case_id: str = "",
        comment: str = "",
        marking_schema: str = "legacy",
        ego_condition: str = "",
        target_behavior: str = "",
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
    ) -> IssueRecord:
        seq_no = len(self.issues) + 1
        safe_problem = problem_tab.replace("/", "-")
        issue_id = f"issue_{seq_no:03d}_{safe_problem}_{format_issue_time(issue_time).replace(':', '').replace(' ', '_').replace('-', '')}"
        issue_dir = self.paths.issues_dir / issue_id
        issue_dir.mkdir(parents=True, exist_ok=True)
        issue = IssueRecord(
            issue_id=issue_id,
            run_id=self.run_id,
            seq_no=seq_no,
            issue_time=issue_time,
            issue_time_text=format_issue_time(issue_time),
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
            clip_start_time=issue_time - 30.0,
            clip_end_time=issue_time + 10.0,
            clip_file=None,
            issue_info_file=str(issue_dir / "issue_info.json"),
            triage=TriageStatus.UNTRIAGED,
            triage_time=None,
            clip_status=ClipStatus.PENDING,
            marking_schema=marking_schema,
            ego_condition=ego_condition,
            target_behavior=target_behavior,
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
        self.issues.append(issue)
        self._persist()
        return issue

    def mark_clip_ready(self, issue_id: str, clip_file: Path) -> None:
        for index, issue in enumerate(self.issues):
            if issue.issue_id == issue_id:
                self.issues[index] = replace(
                    issue,
                    clip_file=str(clip_file),
                    clip_status=ClipStatus.READY,
                )
                self._persist()
                return

    def mark_clip_failed(self, issue_id: str) -> None:
        for index, issue in enumerate(self.issues):
            if issue.issue_id == issue_id:
                self.issues[index] = replace(issue, clip_status=ClipStatus.FAILED)
                self._persist()
                return

    def _persist(self) -> None:
        self.repository.save_issues(self.paths.issues_index_file, self.issues)
        for issue in self.issues:
            self.repository.save_issue_snapshot(Path(issue.issue_info_file), issue)
