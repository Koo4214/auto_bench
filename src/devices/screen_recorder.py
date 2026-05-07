from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from src.app.runtime_tools import resolve_ffmpeg_path
from src.domain.models import SegmentInfo


class ScreenRecorderError(RuntimeError):
    pass


def _subprocess_window_kwargs() -> dict:
    if not sys.platform.startswith("win"):
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


class ScreenSegmentRecorder:
    def __init__(
        self,
        segments_dir: Path,
        ffmpeg_path: Optional[str] = None,
        width: int = 1920,
        height: int = 1080,
        framerate: int = 30,
        segment_time_sec: int = 60,
    ) -> None:
        self.segments_dir = segments_dir
        self.ffmpeg_path = ffmpeg_path or resolve_ffmpeg_path()
        self.width = width
        self.height = height
        self.framerate = framerate
        self.segment_time_sec = segment_time_sec
        self.process: Optional[subprocess.Popen[str]] = None
        self.started_at: Optional[float] = None
        if not self.ffmpeg_path:
            raise ScreenRecorderError("ffmpeg not found")

    def start(self) -> None:
        self.segments_dir.mkdir(parents=True, exist_ok=True)
        output_pattern = str(self.segments_dir / "seg_%06d.mkv")
        command = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "gdigrab",
            "-framerate",
            str(self.framerate),
            "-offset_x",
            "0",
            "-offset_y",
            "0",
            "-video_size",
            f"{self.width}x{self.height}",
            "-i",
            "desktop",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-f",
            "segment",
            "-segment_time",
            str(self.segment_time_sec),
            "-reset_timestamps",
            "1",
            output_pattern,
        ]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            **_subprocess_window_kwargs(),
        )
        self.started_at = time.time()

    def stop(self, timeout_sec: int = 15) -> None:
        if not self.process:
            return
        try:
            if self.process.stdin:
                self.process.stdin.write("q")
                self.process.stdin.flush()
        except OSError:
            pass

        try:
            self.process.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        finally:
            self.process = None

    def stitch(self, output_file: Path) -> None:
        segments = sorted(self.segments_dir.glob("seg_*.mkv"))
        if not segments:
            raise ScreenRecorderError("no screen segments found for stitching")

        concat_file = self.segments_dir / "segments.txt"
        lines = [f"file '{segment.as_posix()}'" for segment in segments]
        concat_file.write_text("\n".join(lines), encoding="utf-8")
        command = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_file),
        ]
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_subprocess_window_kwargs(),
        )

    def build_segment_manifest(self, run_duration_sec: float) -> List[SegmentInfo]:
        segments = sorted(self.segments_dir.glob("seg_*.mkv"))
        manifest: List[SegmentInfo] = []
        for index, path in enumerate(segments):
            start_offset = index * self.segment_time_sec
            end_offset = min(run_duration_sec, start_offset + self.segment_time_sec)
            manifest.append(
                SegmentInfo(
                    index=index,
                    path=path,
                    start_offset_sec=float(start_offset),
                    end_offset_sec=float(end_offset),
                )
            )
        return manifest
