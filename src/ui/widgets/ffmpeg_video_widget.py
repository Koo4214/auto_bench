from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.app.runtime_tools import resolve_ffmpeg_path, resolve_ffprobe_path


class VideoProbeError(RuntimeError):
    pass


FFMPEG_BIN = resolve_ffmpeg_path() or "ffmpeg"
FFPROBE_BIN = resolve_ffprobe_path() or "ffprobe"


def _subprocess_window_kwargs() -> dict:
    if not sys.platform.startswith("win"):
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def _probe_video(path: Path) -> Tuple[int, int, float, float]:
    command = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate:format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    output = subprocess.check_output(
        command,
        text=True,
        encoding="utf-8",
        **_subprocess_window_kwargs(),
    ).strip().splitlines()
    if len(output) < 4:
        raise VideoProbeError(f"Unexpected ffprobe output for {path}")
    width = int(output[0])
    height = int(output[1])
    fps_text = output[2]
    duration = float(output[3]) if output[3] else 0.0
    if "/" in fps_text:
        num, den = fps_text.split("/", 1)
        fps = float(num) / float(den) if float(den) else 30.0
    else:
        fps = float(fps_text)
    return width, height, fps or 30.0, duration


def _fit_size(width: int, height: int, max_width: int, max_height: int) -> Tuple[int, int]:
    if width <= 0 or height <= 0:
        return max_width, max_height
    scale = min(max_width / width, max_height / height)
    scale = min(scale, 1.0)
    target_width = max(2, int(width * scale) // 2 * 2)
    target_height = max(2, int(height * scale) // 2 * 2)
    return target_width, target_height


class _DecodeThread(QThread):
    frame_ready = pyqtSignal(QImage, float, int)
    status_changed = pyqtSignal(str, int)

    def __init__(
        self,
        video_path: Path,
        target_width: int,
        target_height: int,
        start_seconds: float,
        generation: int,
        single_frame: bool,
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.target_width = target_width
        self.target_height = target_height
        self.start_seconds = max(0.0, start_seconds)
        self.generation = generation
        self.single_frame = single_frame
        self._process: Optional[subprocess.Popen[bytes]] = None

    def stop(self) -> None:
        self.requestInterruption()
        if self._process and self._process.poll() is None:
            self._process.kill()
        self.wait(800)

    def run(self) -> None:
        try:
            src_width, src_height, fps, _duration = _probe_video(self.video_path)
            out_width, out_height = _fit_size(src_width, src_height, self.target_width, self.target_height)
            if self.single_frame:
                self._run_single_frame(out_width, out_height)
            else:
                self._run_stream(out_width, out_height, fps)
        except subprocess.CalledProcessError as exc:
            self.status_changed.emit(f"Playback error: {exc}", self.generation)
        except Exception as exc:  # pragma: no cover
            self.status_changed.emit(f"Playback error: {exc}", self.generation)
        finally:
            if self._process and self._process.poll() is None:
                self._process.kill()

    def _run_stream(self, out_width: int, out_height: int, fps: float) -> None:
        frame_size = out_width * out_height * 3
        frame_delay_ms = max(1, int(1000 / max(fps, 1.0)))
        current_seconds = self.start_seconds
        self.status_changed.emit(f"Playing: {self.video_path.name}", self.generation)
        command = [
            FFMPEG_BIN,
            "-loglevel",
            "error",
            "-i",
            str(self.video_path),
            "-ss",
            f"{self.start_seconds:.3f}",
            "-vf",
            f"scale={out_width}:{out_height}",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ]
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_subprocess_window_kwargs(),
        )
        assert self._process.stdout is not None
        while not self.isInterruptionRequested():
            frame_bytes = self._process.stdout.read(frame_size)
            if len(frame_bytes) < frame_size:
                break
            image = QImage(frame_bytes, out_width, out_height, out_width * 3, QImage.Format_RGB888).copy()
            self.frame_ready.emit(image, current_seconds, self.generation)
            current_seconds += 1.0 / max(fps, 1.0)
            self.msleep(frame_delay_ms)
        if not self.isInterruptionRequested():
            self.status_changed.emit(f"Playback finished: {self.video_path.name}", self.generation)

    def _run_single_frame(self, out_width: int, out_height: int) -> None:
        command = [
            FFMPEG_BIN,
            "-loglevel",
            "error",
            "-i",
            str(self.video_path),
            "-ss",
            f"{self.start_seconds:.3f}",
            "-vf",
            f"scale={out_width}:{out_height}",
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ]
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_subprocess_window_kwargs(),
        )
        assert self._process.stdout is not None
        frame_size = out_width * out_height * 3
        frame_bytes = self._process.stdout.read(frame_size)
        if self.isInterruptionRequested():
            return
        if len(frame_bytes) < frame_size:
            raise VideoProbeError("Could not decode frame")
        image = QImage(frame_bytes, out_width, out_height, out_width * 3, QImage.Format_RGB888).copy()
        self.frame_ready.emit(image, self.start_seconds, self.generation)
        self.status_changed.emit(f"Current frame: {self.start_seconds:.1f}s", self.generation)


class FfmpegVideoWidget(QWidget):
    status_changed = pyqtSignal(str)
    busy_changed = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[_DecodeThread] = None
        self._current_path: Optional[Path] = None
        self._current_position = 0.0
        self._duration = 0.0
        self._step_seconds = 1.0
        self._is_playing = False
        self._last_image: Optional[QImage] = None
        self._generation = 0
        self._busy = False
        self._pending_step: float = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.frame_label = QLabel("No clip selected")
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setStyleSheet("background-color: black; color: white;")
        self.frame_label.setMinimumHeight(420)
        layout.addWidget(self.frame_label)

    def set_step_seconds(self, seconds: float) -> None:
        self._step_seconds = max(0.01, seconds)

    def play(self, video_path: Optional[Path] = None) -> None:
        if video_path is not None:
            self._current_path = video_path
            self._current_position = 0.0
            self._duration = 0.0
        if self._current_path is None:
            self.status_changed.emit("No clip selected")
            return
        if self._busy:
            self.status_changed.emit("Player is busy, please wait...")
            return
        self._start_decode(self._current_position, single_frame=False)

    def pause(self) -> None:
        if self._busy:
            return
        self._stop_active_thread()
        self._is_playing = False
        if self._current_path is not None:
            self.status_changed.emit(f"Paused at {self._current_position:.1f}s")

    def step_forward(self) -> None:
        self._queue_step(self._step_seconds)

    def step_backward(self) -> None:
        self._queue_step(-self._step_seconds)

    def stop(self) -> None:
        self._stop_active_thread()
        self._is_playing = False
        self._set_busy(False)
        self._pending_step = 0.0

    def clear(self, message: str) -> None:
        self.stop()
        self._current_path = None
        self._current_position = 0.0
        self._duration = 0.0
        self._last_image = None
        self.frame_label.clear()
        self.frame_label.setText(message)

    def _queue_step(self, delta_seconds: float) -> None:
        if self._current_path is None:
            self.status_changed.emit("No clip selected")
            return
        if self._busy:
            self._pending_step = delta_seconds
            self.status_changed.emit("Step request queued")
            return
        self._run_step(delta_seconds)

    def _run_step(self, delta_seconds: float) -> None:
        self._stop_active_thread()
        self._is_playing = False
        target = max(0.0, self._current_position + delta_seconds)
        if self._duration > 0:
            target = min(target, max(0.0, self._duration - 0.001))
        self._start_decode(target, single_frame=True)

    def _start_decode(self, start_seconds: float, single_frame: bool) -> None:
        assert self._current_path is not None
        self._stop_active_thread()
        self._generation += 1
        width = max(self.frame_label.width(), 960)
        height = max(self.frame_label.height(), 540)
        self._thread = _DecodeThread(
            self._current_path,
            width,
            height,
            start_seconds,
            self._generation,
            single_frame,
        )
        self._thread.frame_ready.connect(self._on_frame_ready)
        self._thread.status_changed.connect(self._on_thread_status)
        self._is_playing = not single_frame
        self._set_busy(True)
        if single_frame:
            self.status_changed.emit(f"Seek to {start_seconds:.1f}s")
        elif self._last_image is None or start_seconds <= 0.001:
            self.frame_label.setText("Loading video...")
        self._thread.start()

    def _stop_active_thread(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread = None

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)

    def _on_frame_ready(self, image: QImage, seconds: float, generation: int) -> None:
        if generation != self._generation:
            return
        self._last_image = image
        self._current_position = seconds
        self._show_image(image)

    def _on_thread_status(self, message: str, generation: int) -> None:
        if generation != self._generation:
            return
        if message.startswith("Playback finished:"):
            self._is_playing = False
            self._thread = None
            self._set_busy(False)
        elif message.startswith("Current frame:"):
            self._thread = None
            self._set_busy(False)
            if self._pending_step != 0.0:
                pending = self._pending_step
                self._pending_step = 0.0
                self._run_step(pending)
                return
        elif message.startswith("Playback error:"):
            self._thread = None
            self._set_busy(False)
        elif message.startswith("Playing:"):
            self._set_busy(False)
        self.status_changed.emit(message)

    def _show_image(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(self.frame_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.frame_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._last_image is not None:
            self._show_image(self._last_image)
