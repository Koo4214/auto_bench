from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional

from src.app.runtime_tools import resolve_ffmpeg_path
from src.domain.models import SegmentInfo


class ClipService:
    def __init__(self, ffmpeg_path: Optional[str] = None) -> None:
        self._explicit_ffmpeg_path = ffmpeg_path
        self._cached_ffmpeg_path: Optional[str] = None

    def _resolve_ffmpeg(self) -> str:
        if self._cached_ffmpeg_path is None:
            self._cached_ffmpeg_path = self._explicit_ffmpeg_path or resolve_ffmpeg_path()
        if not self._cached_ffmpeg_path:
            raise RuntimeError("ffmpeg not found")
        return self._cached_ffmpeg_path

    def create_clip(
        self,
        segments: List[SegmentInfo],
        clip_start_offset_sec: float,
        clip_end_offset_sec: float,
        output_file: Path,
    ) -> None:
        if clip_end_offset_sec <= clip_start_offset_sec:
            raise ValueError("clip end must be after clip start")

        selected = self._select_segments(segments, clip_start_offset_sec, clip_end_offset_sec)
        if not selected:
            raise RuntimeError("no video segments found for clip")

        concat_start = selected[0].start_offset_sec
        relative_start = max(0.0, clip_start_offset_sec - concat_start)
        clip_duration = clip_end_offset_sec - clip_start_offset_sec
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="clip_concat_", dir=str(output_file.parent.parent)) as temp_dir:
            concat_file = Path(temp_dir) / "clip_segments.txt"
            concat_file.write_text(
                "\n".join(f"file '{segment.path.as_posix()}'" for segment in selected),
                encoding="utf-8",
            )
            command = [
                self._resolve_ffmpeg(),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-ss",
                f"{relative_start:.3f}",
                "-t",
                f"{clip_duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                str(output_file),
            ]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _select_segments(
        segments: Iterable[SegmentInfo],
        clip_start_offset_sec: float,
        clip_end_offset_sec: float,
    ) -> List[SegmentInfo]:
        selected: List[SegmentInfo] = []
        for segment in segments:
            overlaps = segment.end_offset_sec > clip_start_offset_sec and segment.start_offset_sec < clip_end_offset_sec
            if overlaps:
                selected.append(segment)
        return selected
