from __future__ import annotations

import csv
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional

try:
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover - runtime environment may miss pyserial
    serial = None
    list_ports = None

from src.devices.rtk_parser import GpchcParser


def list_available_serial_ports() -> List[str]:
    if list_ports is None:
        return []
    return sorted(port.device for port in list_ports.comports())


class RtkSerialDriver:
    mode_label = "serial"

    def __init__(
        self,
        raw_file: Path,
        samples_file: Path,
        serial_port: str = "COM3",
        baudrate: int = 230400,
        cache_size: int = 4096,
    ) -> None:
        self.raw_file = raw_file
        self.samples_file = samples_file
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.cache: Deque[Dict[str, object]] = deque(maxlen=cache_size)
        self._serial = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._writer = None
        self._csv_handle = None
        self._raw_handle = None
        self.connected = False
        self.last_sample: Optional[Dict[str, object]] = None
        self.last_error: Optional[str] = None

    def start(self) -> None:
        self._stop_event.clear()
        self.last_error = None
        self.raw_file.parent.mkdir(parents=True, exist_ok=True)
        self.samples_file.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.connected = False
        try:
            if self._serial is not None:
                self._serial.close()
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._csv_handle:
            self._csv_handle.close()
            self._csv_handle = None
        if self._raw_handle:
            self._raw_handle.close()
            self._raw_handle = None

    def get_latest_location(self) -> tuple[Optional[float], Optional[float]]:
        if not self.last_sample:
            return None, None
        return self.last_sample.get("latitude"), self.last_sample.get("longitude")

    def _run(self) -> None:
        self._open_outputs()
        if serial is None:
            self.last_error = "pyserial unavailable"
            return
        try:
            self._serial = serial.Serial(
                self.serial_port,
                self.baudrate,
                timeout=1.0,
            )
            self.connected = True
            self.last_error = None
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)
            return

        buffer = ""
        try:
            while not self._stop_event.is_set():
                try:
                    chunk = self._serial.read(4096)
                except Exception as exc:
                    self.connected = False
                    self.last_error = str(exc)
                    break
                if not chunk:
                    continue
                buffer += chunk.decode("utf-8", errors="ignore")
                lines = buffer.splitlines(keepends=True)
                if lines and not lines[-1].endswith(("\n", "\r")):
                    buffer = lines.pop()
                else:
                    buffer = ""
                for line in lines:
                    self._handle_line(line.strip())
        finally:
            self.connected = False
            try:
                if self._serial is not None:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _open_outputs(self) -> None:
        self._raw_handle = self.raw_file.open("a", encoding="utf-8")
        self._csv_handle = self.samples_file.open("a", encoding="utf-8", newline="")
        fieldnames = [
            "local_timestamp",
            "gps_week",
            "gps_time",
            "heading",
            "pitch",
            "roll",
            "gyro_x",
            "gyro_y",
            "gyro_z",
            "acc_x",
            "acc_y",
            "acc_z",
            "latitude",
            "longitude",
            "altitude",
            "ve",
            "vn",
            "vu",
            "vehicle_speed",
            "nsv1",
            "nsv2",
            "status",
            "age",
            "warning",
        ]
        self._writer = csv.DictWriter(
            self._csv_handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        if self.samples_file.stat().st_size == 0:
            self._writer.writeheader()
            self._csv_handle.flush()

    def _handle_line(self, line: str) -> None:
        if not line.startswith("$GPCHC"):
            return
        local_timestamp = time.time()
        raw_line = f"{line},{local_timestamp}\n"
        self._raw_handle.write(raw_line)
        self._raw_handle.flush()
        parsed = GpchcParser.parse(line)
        if not parsed:
            return
        parsed["local_timestamp"] = local_timestamp
        self.last_sample = parsed
        self.cache.append(parsed)
        self._writer.writerow(parsed)
        self._csv_handle.flush()
