"""Runtime adapters — bọc vision runtime + NodeState. Persistence repos implement Port trực tiếp."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

from domain.reset_policy import ResetResult, reset_flags_by_order


class CameraRuntimeAdapter:
    def __init__(self, camera_manager) -> None:
        self._mgr = camera_manager

    def is_ready(self) -> bool:
        return self._mgr is not None

    def start_all(self) -> None:
        self._mgr.start_all_cameras()

    def stop_all(self) -> None:
        self._mgr.stop_all_cameras()

    def set_zone_enabled(self, zone: str, on: bool) -> None:
        self._mgr.set_zone_enabled(zone, on)

    def get_status(self) -> Dict[str, Any]:
        return self._mgr.get_status()

    def get_preview_jpeg(self, camera_id: int, detect: bool):
        return self._mgr.get_preview_jpeg(camera_id, detect)

    def get_preview_meta(self, camera_id: int):
        return self._mgr.get_preview_meta(camera_id)

    def get_rtsp_url(self, camera_id: int):
        return self._mgr.get_rtsp_url(camera_id)


class InferenceAdapter:
    def __init__(self, engine) -> None:
        self._eng = engine

    def is_ready(self) -> bool:
        return self._eng is not None

    def pause(self) -> None:
        self._eng.pause()

    def resume(self) -> None:
        self._eng.resume()

    def is_paused(self) -> Optional[bool]:
        try:
            return bool(getattr(self._eng, "_paused").is_set())
        except Exception:
            return None

    def is_model_loaded(self) -> bool:
        try:
            return bool(self._eng.is_model_loaded())
        except Exception:
            return False

    def wait_model_ready(self, timeout: float) -> bool:
        try:
            return bool(self._eng.wait_model_ready(timeout))
        except Exception:
            return False

    def load_error(self) -> Optional[str]:
        try:
            return self._eng.load_error()
        except Exception:
            return None


class NodeStateAdapter:
    def __init__(self, node_state) -> None:
        self._sm = node_state

    def is_ready(self) -> bool:
        return self._sm is not None

    def update_detection(self, node_id: str, detected: bool) -> None:
        self._sm.get_state_nodes(node_id, detected)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._sm.points

    def toggle_flag(self, node_id: str) -> Optional[bool]:
        return self._sm.toggle_flag(node_id)

    def discard_from_ready(self, node_id: str) -> None:
        self._sm.discard_from_ready(node_id)

    def get_detected_start_nodes(self) -> Set[str]:
        return self._sm.get_detected_start_nodes()

    def snapshot_points(self) -> Dict[str, Dict[str, bool]]:
        return self._sm.snapshot_points()

    def apply_reset(self, order_id: str, status: int) -> ResetResult:
        return reset_flags_by_order(self._sm, order_id, status)

    def ready_starts(self) -> Set[str]:
        return set(self._sm.ready_start_list)

    def ready_ends(self) -> Set[str]:
        return set(self._sm.ready_end_list)

    def get_validate_pairs(self) -> Sequence:
        return self._sm.validate_pairs

    def set_pair_used(
        self, start_point: str, end_point: str, order_id: str, empty_car: bool = False
    ) -> None:
        self._sm.set_pair_used(start_point, end_point, order_id, empty_car=empty_car)

    def process_starts(self) -> None:
        self._sm.process_starts()

    def process_ends(self) -> None:
        self._sm.process_ends()


class ZonePairsAdapter:
    def __init__(self, by_zone: Dict[str, List]) -> None:
        self._by_zone = by_zone

    def get_pairs(self, zone: str) -> List:
        return self._by_zone.get(zone.upper(), [])


class RuntimeControlAdapter:
    def __init__(self, runtime_service) -> None:
        self._rt = runtime_service

    async def start(self) -> Dict[str, Any]:
        return await self._rt.start()

    def stop(self) -> Dict[str, Any]:
        return self._rt.stop()

    def status(self) -> Dict[str, Any]:
        return self._rt.status()

    async def reload(self) -> Dict[str, Any]:
        return await self._rt.reload()
