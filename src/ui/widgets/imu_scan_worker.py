from __future__ import annotations

import asyncio
from typing import Dict, List

import bleak
from PyQt5.QtCore import QThread, pyqtSignal


class ImuScanWorker(QThread):
    scan_finished = pyqtSignal(list)
    scan_failed = pyqtSignal(str)

    def __init__(self, preferred_name_contains: str = "WT", timeout_seconds: float = 8.0) -> None:
        super().__init__()
        self.preferred_name_contains = preferred_name_contains
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        try:
            devices = asyncio.run(self._scan_devices())
        except Exception as exc:  # pragma: no cover
            self.scan_failed.emit(str(exc))
            return
        self.scan_finished.emit(devices)

    async def _scan_devices(self) -> List[Dict[str, str]]:
        discovered = await bleak.BleakScanner.discover(timeout=self.timeout_seconds)
        matches: List[Dict[str, str]] = []
        for item in discovered:
            name = getattr(item, "name", None) or ""
            address = getattr(item, "address", None) or ""
            if not address:
                continue
            if self.preferred_name_contains.lower() not in name.lower():
                continue
            matches.append(
                {
                    "name": name or "<unknown>",
                    "address": address,
                }
            )
        matches.sort(key=lambda item: (item["name"], item["address"]))
        return matches
