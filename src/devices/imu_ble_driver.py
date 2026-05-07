from __future__ import annotations

import asyncio
import csv
import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import bleak

from legacy_old_tool import device_model
from src.devices.imu_transform import axis_to_angle_key, compute_steering_angle


class ImuBleDriver:
    SUPPORTED_IMU_LABEL = "WT901 BLE"

    def __init__(
        self,
        raw_file: Path,
        samples_file: Path,
        preferred_address: Optional[str] = None,
        preferred_name_contains: str = "WT",
        steering_axis: str = "Z",
        steering_inverted: bool = False,
    ) -> None:
        self.raw_file = raw_file
        self.samples_file = samples_file
        self.preferred_address = preferred_address
        self.preferred_name_contains = preferred_name_contains
        self.connected = False
        self.connecting = False
        self.has_samples = False
        self.phase = "idle"
        self.last_error: Optional[str] = None
        self.last_sample: Optional[Dict[str, object]] = None
        self.zero_offset_deg = 0.0
        self.steering_axis = steering_axis
        self.steering_angle_key = axis_to_angle_key(steering_axis)
        self.steering_inverted = steering_inverted
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._device = None
        self._selected_ble_device = None
        self._csv_handle = None
        self._writer = None
        self._raw_samples: List[Dict[str, object]] = []
        self._last_discovered_devices: List[Dict[str, str]] = []
        self._io_lock = threading.Lock()
        self._fieldnames = [
            "local_timestamp",
            "acc_x_g",
            "acc_y_g",
            "acc_z_g",
            "gyro_x_dps",
            "gyro_y_dps",
            "gyro_z_dps",
            "angle_x_deg",
            "angle_y_deg",
            "angle_z_deg",
            "steering_axis",
            "steering_inverted",
            "steering_angle_deg",
            "connected",
        ]

    def start(self) -> None:
        self.stop()
        self._stop_event.clear()
        self.last_error = None
        self.last_sample = None
        self.connected = False
        self.connecting = False
        self.has_samples = False
        self.phase = "searching"
        self._angle_correction = 0
        self.raw_file.parent.mkdir(parents=True, exist_ok=True)
        self.samples_file.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._device is not None:
            try:
                self._device.closeDevice()
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        with self._io_lock:
            csv_handle = self._csv_handle
            self._csv_handle = None
            self._writer = None
        if csv_handle:
            csv_handle.close()
        self._flush_raw_json()
        self.connected = False
        self.connecting = False
        if self.phase != "error":
            self.phase = "idle"

    def matches_config(self, preferred_address: Optional[str], steering_axis: str, steering_inverted: bool) -> bool:
        return (
            (self.preferred_address or None) == (preferred_address or None)
            and self.steering_axis == steering_axis
            and self.steering_inverted == steering_inverted
        )

    def redirect_outputs(self, raw_file: Path, samples_file: Path) -> None:
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        samples_file.parent.mkdir(parents=True, exist_ok=True)
        new_handle, new_writer = self._create_csv_writer(samples_file)
        with self._io_lock:
            old_handle = self._csv_handle
            old_raw_file = self.raw_file
            old_raw_samples = list(self._raw_samples)
            self.raw_file = raw_file
            self.samples_file = samples_file
            self._csv_handle = new_handle
            self._writer = new_writer
            self._raw_samples = []
        if old_handle:
            old_handle.close()
        if old_raw_samples:
            old_raw_file.parent.mkdir(parents=True, exist_ok=True)
            with old_raw_file.open("w", encoding="utf-8") as handle:
                json.dump(old_raw_samples, handle, ensure_ascii=False, indent=2)

    def set_steering_axis(self, steering_axis: str) -> None:
        self.steering_axis = steering_axis
        self.steering_angle_key = axis_to_angle_key(steering_axis)
        self._refresh_last_sample_steering()

    def set_steering_inverted(self, steering_inverted: bool) -> None:
        self.steering_inverted = steering_inverted
        self._refresh_last_sample_steering()

    def set_zero(self) -> Optional[float]:
        if not self.last_sample:
            return None
        current = float(self.last_sample.get(self.steering_angle_key, 0.0))
        self.zero_offset_deg = current
        if self.last_sample is not None:
            self.last_sample["steering_angle_deg"] = 0.0
        return self.zero_offset_deg

    def _refresh_last_sample_steering(self) -> None:
        if self.last_sample is None:
            return
        raw_angle = float(self.last_sample.get(self.steering_angle_key, 0.0))
        self.last_sample["steering_axis"] = self.steering_axis
        self.last_sample["steering_inverted"] = self.steering_inverted
        self.last_sample["steering_angle_deg"] = compute_steering_angle(
            raw_angle,
            self.zero_offset_deg,
            inverted=self.steering_inverted,
        )

    def _run(self) -> None:
        asyncio.run(self._async_main())

    async def _async_main(self) -> None:
        self._open_csv_writer()
        try:
            self._selected_ble_device = await self._resolve_device()
            if self._selected_ble_device is None:
                if not self.last_error:
                    self.last_error = f"未发现匹配的 {self.SUPPORTED_IMU_LABEL} 设备。"
                self.phase = "error"
                return
            self.phase = "connecting"
            self.connecting = True
            self._device = device_model.DeviceModel("WT901BLE", self._selected_ble_device, self._handle_device_update)
            self.connected = True
            await self._device.openDevice()
        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False
            self.phase = "error"
        finally:
            self.connected = False
            self.connecting = False
            if self.phase not in ("error", "idle"):
                self.phase = "stopped"
            self._flush_raw_json()

    async def _resolve_device(self):
        if self.preferred_address:
            for _attempt in range(2):
                if self._stop_event.is_set():
                    return None
                direct_device = await bleak.BleakScanner.find_device_by_address(self.preferred_address, timeout=8.0)
                if direct_device is not None:
                    return direct_device
            for _attempt in range(2):
                if self._stop_event.is_set():
                    return None
                devices = await bleak.BleakScanner.discover(timeout=6.0)
                self._remember_discovered_devices(devices)
                picked = self._pick_device(devices, require_exact_address=True)
                if picked is not None:
                    return picked
            self.last_error = self._build_not_found_message(address_only=True)
            return None
        for _attempt in range(3):
            if self._stop_event.is_set():
                return None
            devices = await bleak.BleakScanner.discover(timeout=6.0)
            self._remember_discovered_devices(devices)
            picked = self._pick_device(devices)
            if picked is not None:
                return picked
        self.last_error = self._build_not_found_message(address_only=False)
        return None

    def _pick_device(self, devices, require_exact_address: bool = False) -> Optional[object]:
        if self.preferred_address:
            for item in devices:
                if self._matches_address(getattr(item, "address", None), self.preferred_address):
                    return item
            if require_exact_address:
                return None
        for item in devices:
            if item.name and self.preferred_name_contains.lower() in item.name.lower():
                return item
        return None

    def _remember_discovered_devices(self, devices) -> None:
        remembered = []
        for item in devices:
            name = getattr(item, "name", None) or "<unknown>"
            address = getattr(item, "address", None) or "<no-address>"
            remembered.append({"name": name, "address": address})
        self._last_discovered_devices = remembered

    def _build_not_found_message(self, address_only: bool) -> str:
        if address_only and self.preferred_address:
            prefix = f"未找到蓝牙地址为 {self.preferred_address} 的 {self.SUPPORTED_IMU_LABEL} 设备。"
        else:
            prefix = f"未扫描到名称包含“{self.preferred_name_contains}”的 {self.SUPPORTED_IMU_LABEL} 设备。"
        if not self._last_discovered_devices:
            return prefix
        visible_devices = ", ".join(
            f"{item['name']}({item['address']})" for item in self._last_discovered_devices[:6]
        )
        return f"{prefix} 当前扫描到: {visible_devices}"

    @staticmethod
    def _matches_address(left: Optional[str], right: Optional[str]) -> bool:
        if not left or not right:
            return False
        return left.strip().lower() == right.strip().lower()

    def _handle_device_update(self, model: device_model.DeviceModel) -> None:
        data = dict(model.deviceData)
        sample = {
            "local_timestamp": time.time(),
            "acc_x_g": float(data.get("AccX", 0.0)),
            "acc_y_g": float(data.get("AccY", 0.0)),
            "acc_z_g": float(data.get("AccZ", 0.0)),
            "gyro_x_dps": float(data.get("AsX", 0.0)),
            "gyro_y_dps": float(data.get("AsY", 0.0)),
            "gyro_z_dps": float(data.get("AsZ", 0.0)),
            "angle_x_deg": float(data.get("AngX", 0.0)),
            "angle_y_deg": float(data.get("AngY", 0.0)),
            "angle_z_deg": float(data.get("AngZ", 0.0)),
            "steering_axis": self.steering_axis,
            "steering_inverted": self.steering_inverted,
            "steering_angle_deg": 0.0,
            "connected": True,
        }
        raw_angle = float(sample.get(self.steering_angle_key, 0.0))
        sample["steering_angle_deg"] = compute_steering_angle(
            raw_angle,
            self.zero_offset_deg,
            inverted=self.steering_inverted,
        )
        sample["steering_angle_deg"] = self._normalize_steering_angle(sample["local_timestamp"], sample["steering_angle_deg"])
        self.last_sample = sample
        self.has_samples = True
        self.phase = "streaming"
        self.last_error = None
        with self._io_lock:
            self._raw_samples.append(sample)
            if self._writer is not None and self._csv_handle is not None:
                try:
                    self._writer.writerow(sample)
                    self._csv_handle.flush()
                except Exception as exc:
                    self.last_error = f"IMU 数据写入失败: {exc}"

    # 修正方向盘角度
    def _normalize_steering_angle(self, current_ts, current_angle):
        if self.last_sample:
            # 解决角度跳变问题
            current_angle += self._angle_correction
            if current_ts - self.last_sample["local_timestamp"] < 0.25:
                d_angle = current_angle - self.last_sample["steering_angle_deg"]
                if d_angle > 270:
                    self._angle_correction -= 360
                    current_angle -= 360
                elif d_angle < -270:
                    self._angle_correction += 360
                    current_angle += 360
            
            # 限制最多转1.5圈
            if current_angle > 540:
                current_angle = 540
            elif current_angle < -540:
                current_angle = -540
        return current_angle

    def _create_csv_writer(self, samples_file: Path):
        handle = samples_file.open("a", encoding="utf-8", newline="")
        writer = csv.DictWriter(handle, fieldnames=self._fieldnames)
        if samples_file.stat().st_size == 0:
            writer.writeheader()
            handle.flush()
        return handle, writer

    def _open_csv_writer(self) -> None:
        handle, writer = self._create_csv_writer(self.samples_file)
        with self._io_lock:
            old_handle = self._csv_handle
            self._csv_handle = handle
            self._writer = writer
        if old_handle:
            old_handle.close()

    def _flush_raw_json(self) -> None:
        with self._io_lock:
            raw_file = self.raw_file
            payload = list(self._raw_samples)
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        with raw_file.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
