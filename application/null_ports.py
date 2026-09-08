"""Null / unbound runtime ports — used before RuntimeService.start()."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Set

from domain.reset_policy import ResetResult


class NullCameraRuntime:
    def is_ready(self) -> bool:
        return False

    def start_all(self) -> None:
        return None

    def stop_all(self) -> None:
        return None

    def set_zone_enabled(self, zone: str, on: bool) -> None:
        return None

    def get_status(self) -> Dict[str, Any]:
        return {"total": 0, "enabled": 0, "alive": 0, "streaming": 0, "cameras": []}

    def get_preview_jpeg(self, camera_id: int, detect: bool):
        return None, "Runtime not started", 503

    def get_preview_meta(self, camera_id: int):
        return None, "Runtime not started", 503

    def get_rtsp_url(self, camera_id: int):
        return None


class NullInference:
    def is_ready(self) -> bool:
        return False

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None

    def is_paused(self) -> Optional[bool]:
        return None

    def is_model_loaded(self) -> bool:
        return False

    def wait_model_ready(self, timeout: float) -> bool:
        return False

    def load_error(self) -> Optional[str]:
        return None


class NullNodeStateStore:
    def is_ready(self) -> bool:
        return False

    def update_detection(self, node_id: str, detected: bool) -> None:
        return None

    def has_node(self, node_id: str) -> bool:
        return False

    def toggle_flag(self, node_id: str) -> Optional[bool]:
        return None

    def discard_from_ready(self, node_id: str) -> None:
        return None

    def get_detected_start_nodes(self) -> Set[str]:
        return set()

    def snapshot_points(self) -> Dict[str, Dict[str, bool]]:
        return {}

    def apply_reset(self, order_id: str, status: int) -> ResetResult:
        return ResetResult(success=False, message="", order_id=order_id, error="not ready")

    def ready_starts(self) -> Set[str]:
        return set()

    def ready_ends(self) -> Set[str]:
        return set()

    def get_validate_pairs(self) -> Sequence:
        return []

    def set_pair_used(
        self, start_point: str, end_point: str, order_id: str, empty_car: bool = False
    ) -> None:
        return None

    def process_starts(self) -> None:
        return None

    def process_ends(self) -> None:
        return None


class NullDispatchGateway:
    def send(self, payload: Dict[str, Any]) -> bool:
        return False


class NullDbHealth:
    async def ping(self) -> bool:
        return False


class NullWebrtcRunner:
    def status(self) -> Dict[str, Any]:
        return {"alive": False, "owned": False, "watchdog": False}


class NullFrameProvider:
    def capture_for_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return None


class NullRuntimeControl:
    async def start(self) -> Dict[str, Any]:
        return {"running": False}

    def stop(self) -> Dict[str, Any]:
        return {"running": False}

    def status(self) -> Dict[str, Any]:
        return {"running": False}

    async def reload(self) -> Dict[str, Any]:
        return {"running": False}


class NullCameraConfigRepo:
    async def get_all(self):
        return []

    async def get_by_area(self, area: str):
        return []

    async def create(self, doc):
        return ""

    async def update_by_camera_id(self, camera_id, data):
        return False

    async def delete_by_camera_id(self, camera_id):
        return False


class NullPairsRepo:
    async def get_by_zone(self, zone_id):
        return []

    async def set_enabled(self, start_point, end_point, enabled):
        return False

    async def create(self, doc):
        return ""

    async def delete(self, start_point, end_point):
        return False

    async def get_as_tuples(self):
        return []


class NullNodeRepo:
    async def get_by_zone(self, zone_id):
        return []

    async def get_by_id(self, node_id):
        return None

    async def get_by_camera(self, camera_id):
        return []

    async def set_enabled(self, node_id, enabled):
        return False

    async def set_camera_nodes_enabled(self, camera_id, enabled):
        return 0

    async def update_priority(self, node_id, priority):
        return False

    async def create(self, doc):
        return ""

    async def delete_by_node_id(self, node_id):
        return False

