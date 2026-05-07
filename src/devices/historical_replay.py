from __future__ import annotations

import csv
import json
import shutil
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

from src.devices.imu_transform import axis_to_angle_key, compute_steering_angle
from src.devices.rtk_parser import GpchcParser

RTK_FIELDS = [
    'local_timestamp', 'gps_week', 'gps_time', 'heading', 'pitch', 'roll', 'gyro_x', 'gyro_y', 'gyro_z',
    'acc_x', 'acc_y', 'acc_z', 'latitude', 'longitude', 'altitude', 've', 'vn', 'vu', 'vehicle_speed',
    'nsv1', 'nsv2', 'status', 'age', 'warning',
]

IMU_FIELDS = [
    'local_timestamp', 'acc_x_g', 'acc_y_g', 'acc_z_g', 'gyro_x_dps', 'gyro_y_dps', 'gyro_z_dps',
    'angle_x_deg', 'angle_y_deg', 'angle_z_deg', 'steering_axis', 'steering_inverted', 'steering_angle_deg', 'connected',
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class HistoricalRtkReplayDriver:
    def __init__(self, source_dir: Path, raw_file: Path, samples_file: Path, cache_size: int = 4096) -> None:
        self.source_dir = source_dir
        self.raw_file = raw_file
        self.samples_file = samples_file
        self.cache: Deque[Dict[str, object]] = deque(maxlen=cache_size)
        self.connected = False
        self.last_sample: Optional[Dict[str, object]] = None
        self.last_error: Optional[str] = None
        self.mode_label = 'replay'
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._samples: List[Dict[str, object]] = []

    @staticmethod
    def has_source(source_dir: Path) -> bool:
        return (source_dir / 'rtk_samples.csv').exists() or (source_dir / 'rtk.txt').exists()

    def start(self) -> None:
        self.stop()
        self.last_error = None
        self._samples = self._load_samples()
        if not self._samples:
            self.last_error = 'No RTK replay samples found'
            return
        self._copy_outputs()
        self._stop_event.clear()
        self.connected = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self.connected = False

    def get_latest_location(self) -> Tuple[Optional[float], Optional[float]]:
        if not self.last_sample:
            return None, None
        return self.last_sample.get('latitude'), self.last_sample.get('longitude')

    def _run(self) -> None:
        while not self._stop_event.is_set():
            previous_ts: Optional[float] = None
            for sample in self._samples:
                if self._stop_event.is_set():
                    return
                sample_copy = dict(sample)
                now = time.time()
                sample_copy['local_timestamp'] = now
                self.last_sample = sample_copy
                self.cache.append(sample_copy)
                sample_ts = _safe_float(sample.get('local_timestamp'), now)
                delay = 0.05
                if previous_ts is not None:
                    delay = max(0.01, min(0.1, sample_ts - previous_ts))
                previous_ts = sample_ts
                time.sleep(delay)

    def _copy_outputs(self) -> None:
        self.raw_file.parent.mkdir(parents=True, exist_ok=True)
        self.samples_file.parent.mkdir(parents=True, exist_ok=True)
        source_csv = self.source_dir / 'rtk_samples.csv'
        source_raw = self.source_dir / 'rtk.txt'
        if source_csv.exists():
            shutil.copyfile(source_csv, self.samples_file)
        else:
            with self.samples_file.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=RTK_FIELDS)
                writer.writeheader()
                for sample in self._samples:
                    writer.writerow({key: sample.get(key) for key in RTK_FIELDS})
        if source_raw.exists():
            shutil.copyfile(source_raw, self.raw_file)
        else:
            self.raw_file.write_text('', encoding='utf-8')

    def _load_samples(self) -> List[Dict[str, object]]:
        source_csv = self.source_dir / 'rtk_samples.csv'
        if source_csv.exists():
            rows: List[Dict[str, object]] = []
            with source_csv.open('r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    rows.append({
                        'local_timestamp': _safe_float(row.get('local_timestamp')),
                        'gps_week': _safe_int(row.get('gps_week')),
                        'gps_time': _safe_float(row.get('gps_time')),
                        'heading': _safe_float(row.get('heading')),
                        'pitch': _safe_float(row.get('pitch')),
                        'roll': _safe_float(row.get('roll')),
                        'gyro_x': _safe_float(row.get('gyro_x')),
                        'gyro_y': _safe_float(row.get('gyro_y')),
                        'gyro_z': _safe_float(row.get('gyro_z')),
                        'acc_x': _safe_float(row.get('acc_x')),
                        'acc_y': _safe_float(row.get('acc_y')),
                        'acc_z': _safe_float(row.get('acc_z')),
                        'latitude': _safe_float(row.get('latitude')),
                        'longitude': _safe_float(row.get('longitude')),
                        'altitude': _safe_float(row.get('altitude')),
                        've': _safe_float(row.get('ve')),
                        'vn': _safe_float(row.get('vn')),
                        'vu': _safe_float(row.get('vu')),
                        'vehicle_speed': _safe_float(row.get('vehicle_speed')),
                        'nsv1': _safe_int(row.get('nsv1')),
                        'nsv2': _safe_int(row.get('nsv2')),
                        'status': _safe_int(row.get('status')),
                        'age': _safe_int(row.get('age')),
                        'warning': _safe_int(row.get('warning')),
                    })
            return rows

        source_raw = self.source_dir / 'rtk.txt'
        rows = []
        if source_raw.exists():
            for line in source_raw.read_text(encoding='utf-8', errors='ignore').splitlines():
                raw_line = line.strip()
                if not raw_line:
                    continue
                gpchc_line = raw_line
                local_timestamp = time.time()
                if ',' in raw_line:
                    possible_line, possible_ts = raw_line.rsplit(',', 1)
                    if possible_line.startswith('$GPCHC'):
                        gpchc_line = possible_line
                        local_timestamp = _safe_float(possible_ts, time.time())
                parsed = GpchcParser.parse(gpchc_line)
                if not parsed:
                    continue
                parsed['local_timestamp'] = local_timestamp
                rows.append(parsed)
        return rows


class HistoricalImuReplayDriver:
    def __init__(
        self,
        source_dir: Path,
        raw_file: Path,
        samples_file: Path,
        steering_axis: str = 'Z',
        steering_inverted: bool = False,
    ) -> None:
        self.source_dir = source_dir
        self.raw_file = raw_file
        self.samples_file = samples_file
        self.steering_axis = steering_axis
        self.steering_angle_key = axis_to_angle_key(steering_axis)
        self.steering_inverted = steering_inverted
        self.zero_offset_deg = 0.0
        self.connected = False
        self.connecting = False
        self.has_samples = False
        self.phase = 'idle'
        self.last_error: Optional[str] = None
        self.last_sample: Optional[Dict[str, object]] = None
        self.mode_label = 'replay'
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._samples: List[Dict[str, object]] = []

    @staticmethod
    def has_source(source_dir: Path) -> bool:
        return (source_dir / 'imu_samples.csv').exists() or (source_dir / 'imu_data.json').exists()

    def start(self) -> None:
        self.stop()
        self.last_error = None
        self._samples = self._load_samples()
        if not self._samples:
            self.last_error = 'No IMU replay samples found'
            self.phase = 'error'
            return
        self._copy_outputs()
        self._stop_event.clear()
        self.connected = True
        self.has_samples = True
        self.phase = 'streaming'
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self.connected = False
        if self.phase != 'error':
            self.phase = 'idle'

    def set_zero(self) -> Optional[float]:
        if not self.last_sample:
            return None
        current = float(self.last_sample.get(self.steering_angle_key, 0.0))
        self.zero_offset_deg = current
        self._refresh_last_sample_steering()
        return self.zero_offset_deg

    def _refresh_last_sample_steering(self) -> None:
        if self.last_sample is None:
            return
        raw_angle = float(self.last_sample.get(self.steering_angle_key, 0.0))
        self.last_sample['steering_axis'] = self.steering_axis
        self.last_sample['steering_inverted'] = self.steering_inverted
        self.last_sample['steering_angle_deg'] = compute_steering_angle(raw_angle, self.zero_offset_deg, inverted=self.steering_inverted)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            previous_ts: Optional[float] = None
            for sample in self._samples:
                if self._stop_event.is_set():
                    return
                sample_copy = dict(sample)
                now = time.time()
                sample_copy['local_timestamp'] = now
                raw_angle = float(sample_copy.get(self.steering_angle_key, 0.0))
                sample_copy['steering_axis'] = self.steering_axis
                sample_copy['steering_inverted'] = self.steering_inverted
                sample_copy['steering_angle_deg'] = compute_steering_angle(raw_angle, self.zero_offset_deg, inverted=self.steering_inverted)
                self.last_sample = sample_copy
                sample_ts = _safe_float(sample.get('local_timestamp'), now)
                delay = 0.08
                if previous_ts is not None:
                    delay = max(0.02, min(0.12, sample_ts - previous_ts))
                previous_ts = sample_ts
                time.sleep(delay)

    def _copy_outputs(self) -> None:
        self.raw_file.parent.mkdir(parents=True, exist_ok=True)
        self.samples_file.parent.mkdir(parents=True, exist_ok=True)
        source_csv = self.source_dir / 'imu_samples.csv'
        source_raw = self.source_dir / 'imu_data.json'
        if source_csv.exists():
            shutil.copyfile(source_csv, self.samples_file)
        else:
            with self.samples_file.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=IMU_FIELDS)
                writer.writeheader()
                for sample in self._samples:
                    payload = {key: sample.get(key) for key in IMU_FIELDS}
                    payload['steering_axis'] = self.steering_axis
                    payload['steering_inverted'] = self.steering_inverted
                    writer.writerow(payload)
        if source_raw.exists():
            shutil.copyfile(source_raw, self.raw_file)
        else:
            with self.raw_file.open('w', encoding='utf-8') as handle:
                json.dump(self._samples, handle, ensure_ascii=False, indent=2)

    def _load_samples(self) -> List[Dict[str, object]]:
        source_csv = self.source_dir / 'imu_samples.csv'
        if source_csv.exists():
            rows: List[Dict[str, object]] = []
            with source_csv.open('r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    rows.append({
                        'local_timestamp': _safe_float(row.get('local_timestamp')),
                        'acc_x_g': _safe_float(row.get('acc_x_g')),
                        'acc_y_g': _safe_float(row.get('acc_y_g')),
                        'acc_z_g': _safe_float(row.get('acc_z_g')),
                        'gyro_x_dps': _safe_float(row.get('gyro_x_dps')),
                        'gyro_y_dps': _safe_float(row.get('gyro_y_dps')),
                        'gyro_z_dps': _safe_float(row.get('gyro_z_dps')),
                        'angle_x_deg': _safe_float(row.get('angle_x_deg')),
                        'angle_y_deg': _safe_float(row.get('angle_y_deg')),
                        'angle_z_deg': _safe_float(row.get('angle_z_deg')),
                        'steering_angle_deg': _safe_float(row.get('steering_angle_deg')),
                        'connected': True,
                    })
            return rows

        source_raw = self.source_dir / 'imu_data.json'
        rows = []
        if source_raw.exists():
            payload = json.loads(source_raw.read_text(encoding='utf-8', errors='ignore'))
            if isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    rows.append({
                        'local_timestamp': _safe_float(item.get('local_timestamp') or item.get('timestamp') or item.get('time')),
                        'acc_x_g': _safe_float(item.get('acc_x_g') or item.get('AccX')),
                        'acc_y_g': _safe_float(item.get('acc_y_g') or item.get('AccY')),
                        'acc_z_g': _safe_float(item.get('acc_z_g') or item.get('AccZ')),
                        'gyro_x_dps': _safe_float(item.get('gyro_x_dps') or item.get('AsX')),
                        'gyro_y_dps': _safe_float(item.get('gyro_y_dps') or item.get('AsY')),
                        'gyro_z_dps': _safe_float(item.get('gyro_z_dps') or item.get('AsZ')),
                        'angle_x_deg': _safe_float(item.get('angle_x_deg') or item.get('AngX')),
                        'angle_y_deg': _safe_float(item.get('angle_y_deg') or item.get('AngY')),
                        'angle_z_deg': _safe_float(item.get('angle_z_deg') or item.get('AngZ')),
                        'steering_angle_deg': 0.0,
                        'connected': True,
                    })
        return rows
