from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PyQt5.QtMultimedia import QCamera, QCameraInfo
from PyQt5.QtMultimediaWidgets import QCameraViewfinder


class CameraPreviewManager:
    def __init__(self, camera_count: int = 2) -> None:
        self.camera_count = camera_count
        self.viewfinders: List[QCameraViewfinder] = []
        self.cameras: List[QCamera] = []
        self.slot_states: List[Dict[str, object]] = [
            self._empty_state(index) for index in range(camera_count)
        ]

    def bind_viewfinders(self, viewfinders: Sequence[QCameraViewfinder]) -> None:
        self.viewfinders = list(viewfinders[: self.camera_count])
        for index in range(self.camera_count):
            state = self.slot_states[index]
            state["bound"] = index < len(self.viewfinders)
            if not state["bound"]:
                state["error"] = "未绑定预览窗口"
            self.slot_states[index] = state

    def list_available_cameras(self) -> List[Dict[str, str]]:
        return [
            {
                "device_name": camera.deviceName(),
                "description": camera.description(),
            }
            for camera in QCameraInfo.availableCameras()
        ]

    def start(self, selected_devices: Optional[Sequence[str]] = None) -> None:
        self.stop()
        camera_infos = QCameraInfo.availableCameras()
        selected_infos = self._select_cameras(camera_infos, selected_devices)
        for index in range(self.camera_count):
            state = self._empty_state(index)
            state["bound"] = index < len(self.viewfinders)
            if index >= len(selected_infos):
                state["error"] = "未找到选定相机"
                self.slot_states[index] = state
                continue
            if index >= len(self.viewfinders):
                state["description"] = selected_infos[index].description()
                state["error"] = "未绑定预览窗口"
                self.slot_states[index] = state
                continue

            camera_info = selected_infos[index]
            camera = QCamera(camera_info)
            camera.setViewfinder(self.viewfinders[index])
            camera.statusChanged.connect(self._make_status_handler(index))
            camera.stateChanged.connect(self._make_state_handler(index))
            camera.error.connect(self._make_error_handler(index))
            state["description"] = camera_info.description()
            state["device_name"] = camera_info.deviceName()
            state["connected"] = True
            self.slot_states[index] = state
            self.cameras.append(camera)
            camera.start()

    def stop(self) -> None:
        for camera in self.cameras:
            try:
                camera.stop()
            except Exception:
                pass
            camera.deleteLater()
        self.cameras = []
        for index, state in enumerate(self.slot_states):
            state["active"] = False
            if state.get("connected"):
                state["connected"] = False
                if not state.get("error"):
                    state["error"] = "已停止"
            if not state.get("bound"):
                state["error"] = "未绑定预览窗口"
            self.slot_states[index] = state

    def get_snapshot(self) -> List[Dict[str, object]]:
        return [dict(state) for state in self.slot_states]

    def _select_cameras(
        self,
        camera_infos: Sequence[QCameraInfo],
        selected_devices: Optional[Sequence[str]],
    ) -> List[QCameraInfo]:
        if not selected_devices:
            return list(camera_infos[: self.camera_count])

        by_name = {camera.deviceName(): camera for camera in camera_infos}
        selected_infos: List[QCameraInfo] = []
        for device_name in selected_devices[: self.camera_count]:
            camera = by_name.get(device_name)
            if camera is not None:
                selected_infos.append(camera)
        return selected_infos

    def _make_status_handler(self, slot_index: int):
        def _handler(status: QCamera.Status) -> None:
            state = self.slot_states[slot_index]
            state["status"] = int(status)
            if status == QCamera.ActiveStatus:
                state["active"] = True
                state["error"] = None
            elif status in (QCamera.LoadedStatus, QCamera.StartingStatus):
                state["active"] = False
            elif status == QCamera.UnavailableStatus:
                state["active"] = False
                state["error"] = "相机不可用"
            self.slot_states[slot_index] = state

        return _handler

    def _make_state_handler(self, slot_index: int):
        def _handler(state_value: QCamera.State) -> None:
            state = self.slot_states[slot_index]
            state["active"] = state_value == QCamera.ActiveState
            self.slot_states[slot_index] = state

        return _handler

    def _make_error_handler(self, slot_index: int):
        def _handler(*_args: object) -> None:
            state = self.slot_states[slot_index]
            camera = self._camera_for_slot(slot_index)
            state["active"] = False
            state["error"] = camera.errorString() if camera else "相机错误"
            self.slot_states[slot_index] = state

        return _handler

    def _camera_for_slot(self, slot_index: int) -> Optional[QCamera]:
        if 0 <= slot_index < len(self.cameras):
            return self.cameras[slot_index]
        return None

    @staticmethod
    def _empty_state(slot_index: int) -> Dict[str, object]:
        return {
            "slot_index": slot_index,
            "description": None,
            "device_name": None,
            "bound": False,
            "connected": False,
            "active": False,
            "status": None,
            "error": None,
        }
