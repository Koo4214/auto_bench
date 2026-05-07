from __future__ import annotations

from pathlib import Path
from typing import List

from src.domain.models import IssueRecord, RunMeta, RunStatus
from src.storage.json_io import read_json, write_json_atomic


class RunRepository:
    def save_meta(self, path: Path, meta: RunMeta) -> None:
        write_json_atomic(path, meta.to_dict())

    def save_status(self, path: Path, status: RunStatus) -> None:
        write_json_atomic(path, status.to_dict())


class IssueRepository:
    def load_issues(self, path: Path) -> List[dict]:
        return read_json(path, [])

    def save_issues(self, path: Path, issues: List[IssueRecord]) -> None:
        write_json_atomic(path, [issue.to_dict() for issue in issues])

    def save_issue_snapshot(self, path: Path, issue: IssueRecord) -> None:
        write_json_atomic(path, issue.to_dict())
