from __future__ import annotations

import csv
import socket
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional, Set

from src.devices.rtk_parser import GpchcParser


class RtkLiveDriver:
    def __init__(
        self,
        raw_file: Path,
        samples_file: Path,
        host: str = "192.168.30.1",
        port: int = 9901,
        cache_size: int = 4096,
        bind_host: Optional[str] = None,
        mode: str = "auto",
    ) -> None:
        self.raw_file = raw_file
        self.samples_file = samples_file
        self.host = host
        self.port = port
        self.bind_host = bind_host or host
        self.mode = mode
        self.cache: Deque[Dict[str, object]] = deque(maxlen=cache_size)
        self._server_socket: Optional[socket.socket] = None
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
            if self._server_socket is not None:
                self._server_socket.close()
        except OSError:
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
        try:
            mode = self._resolve_mode()
            if mode == "connect":
                self._run_connect_mode()
            else:
                self._run_listen_mode()
        finally:
            self.connected = False
            try:
                if self._server_socket is not None:
                    self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

    def _resolve_mode(self) -> str:
        if self.mode in {"listen", "connect"}:
            return self.mode
        return "listen" if self.host in self._local_ipv4s() else "connect"

    @staticmethod
    def _local_ipv4s() -> Set[str]:
        ips = {"127.0.0.1", "0.0.0.0", "localhost"}
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ips.add(info[4][0])
        except OSError:
            pass
        return ips

    def _run_listen_mode(self) -> None:
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            self._server_socket.settimeout(1.0)
            self._server_socket.bind((self.bind_host, self.port))
            self._server_socket.listen(1)
            while not self._stop_event.is_set():
                try:
                    conn, _addr = self._server_socket.accept()
                except socket.timeout:
                    continue
                except OSError as exc:
                    self.last_error = str(exc)
                    break
                self._consume_socket(conn)
        except OSError as exc:
            self.last_error = str(exc)

    def _run_connect_mode(self) -> None:
        while not self._stop_event.is_set():
            try:
                conn = socket.create_connection((self.host, self.port), timeout=3.0)
            except OSError as exc:
                self.last_error = str(exc)
                self.connected = False
                time.sleep(1.0)
                continue
            self.last_error = None
            self._consume_socket(conn)
            if not self._stop_event.is_set():
                time.sleep(0.5)

    def _consume_socket(self, conn: socket.socket) -> None:
        with conn:
            self.connected = True
            conn.settimeout(1.0)
            buffer = ""
            while not self._stop_event.is_set():
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        self.connected = False
                        break
                    buffer += chunk.decode("utf-8", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        self._handle_line(line.strip())
                except socket.timeout:
                    continue
                except OSError as exc:
                    self.last_error = str(exc)
                    self.connected = False
                    break
            self.connected = False

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
