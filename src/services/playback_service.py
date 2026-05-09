from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

from src.domain.test_functions import DEFAULT_TEST_FUNCTION, normalize_test_function
from src.storage.json_io import read_json, write_json_atomic


class PlaybackService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def set_base_dir(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def list_runs(self) -> List[Dict[str, object]]:
        runs: List[Dict[str, object]] = []
        if not self.base_dir.exists():
            return runs

        status_paths: List[Path]
        if (self.base_dir / 'status.json').exists():
            status_paths = [self.base_dir / 'status.json']
        else:
            status_paths = list(self.base_dir.rglob('status.json'))

        for status_path in status_paths:
            run_root = status_path.parent
            meta_path = run_root / 'meta.json'
            status = read_json(status_path, {})
            meta = read_json(meta_path, {})
            run_id = status.get('run_id') or meta.get('run_id') or run_root.name
            vehicle = meta.get('vehicle_model', '-')
            vehicle_id = meta.get('vehicle_id', '-')
            test_function = normalize_test_function(meta.get('test_function', DEFAULT_TEST_FUNCTION))
            test_date = meta.get('test_date', run_root.parent.parent.name if len(run_root.parts) >= 3 else '-')
            state = status.get('state', 'unknown')
            issue_count = status.get('issue_count', 0)
            ended_at = status.get('ended_at') or status.get('started_at') or 0
            runs.append(
                {
                    'run_id': run_id,
                    'run_root': str(run_root),
                    'display_name': f"{test_date} | {vehicle} | {vehicle_id} | {run_id} | {state} | issues={issue_count}",
                    'vehicle_model': vehicle,
                    'vehicle_id': vehicle_id,
                    'test_function': test_function,
                    'test_date': test_date,
                    'state': state,
                    'issue_count': issue_count,
                    'sort_key': float(ended_at or 0),
                }
            )

        runs.sort(key=lambda item: item['sort_key'], reverse=True)
        return runs

    def load_issues(self, run_root: Path) -> List[Dict[str, object]]:
        issues_path = run_root / 'issues' / 'issues.json'
        issues = read_json(issues_path, [])
        return issues if isinstance(issues, list) else []

    def update_issue(self, run_root: Path, issue_id: str, updates: Dict[str, object]) -> Dict[str, object]:
        issues_path = run_root / 'issues' / 'issues.json'
        issues = self.load_issues(run_root)
        updated_issue: Optional[Dict[str, object]] = None
        triage_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        for issue in issues:
            if issue.get('issue_id') == issue_id:
                issue.update(updates)
                issue['triage'] = 'triaged'
                issue['triage_time'] = triage_time
                updated_issue = issue
                break

        if updated_issue is None:
            raise RuntimeError(f'Issue not found: {issue_id}')

        write_json_atomic(issues_path, issues)

        info_path = Path(updated_issue.get('issue_info_file', ''))
        if not info_path.is_absolute():
            info_path = run_root / info_path
        if info_path.exists() or str(info_path):
            payload = read_json(info_path, {}) if info_path.exists() else {}
            payload.update(updated_issue)
            write_json_atomic(info_path, payload)

        return updated_issue

    def resolve_clip_path(self, run_root: Path, issue: Dict[str, object]) -> Optional[Path]:
        clip_file = issue.get('clip_file')
        if not clip_file:
            return None
        clip_path = Path(str(clip_file))
        if clip_path.is_absolute():
            return clip_path
        return run_root / clip_path
