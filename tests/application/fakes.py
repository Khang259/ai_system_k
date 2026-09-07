"""Fake ports for application unit tests — no Mongo / GPU / RTSP."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

from domain.node_state import NodeState
from domain.reset_policy import ResetResult, reset_flags_by_order


class FakeCameraRuntime:
    def __init__(
        self,
        ready: bool = True,
        enabled: int = 1,
        streaming: int = 1,
        cameras: Optional[List[Dict[str, Any]]] = None,
        auto_stream: bool = True,
    ) -> None:
        self.ready = ready
        self.enabled = enabled
        self.total = 2
        self.alive = 1
        self.streaming = streaming
        self.cameras = cameras or []
        self.auto_stream = auto_stream
        self.started_all = False
        self.stopped_all = False
        self.zone_calls: List[tuple] = []

    def is_ready(self) -> bool:
        return self.ready

    def start_all(self) -> None:
        self.started_all = True
        self.enabled = self.total
        if not self.auto_stream:
            return
        if not self.cameras:
            self.cameras = [
                {"cam_id": "cam_0", "enabled": True, "streaming": True, "error": None},
                {"cam_id": "cam_1", "enabled": True, "streaming": False, "error": "rtsp timeout"},
            ]
            self.streaming = 1

    def stop_all(self) -> None:
        self.stopped_all = True
        self.enabled = 0
        self.streaming = 0

    def set_zone_enabled(self, zone: str, on: bool) -> None:
        self.zone_calls.append((zone, on))
        self.enabled = 1 if on else 0

    def get_status(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "enabled": self.enabled,
            "alive": self.alive,
            "streaming": self.streaming,
            "cameras": self.cameras,
        }

    def get_preview_jpeg(self, camera_id: int, detect: bool):
        if getattr(self, "preview_missing", False):
            return None, "Camera not found", 404
        if getattr(self, "preview_offline", False):
            return None, "Camera not streaming", 409
        jpeg = getattr(self, "preview_jpeg", None)
        if jpeg is None:
            return None, "No preview yet", 503
        return jpeg, None, 200

    def get_preview_meta(self, camera_id: int):
        if getattr(self, "preview_missing", False):
            return None, "Camera not found", 404
        if getattr(self, "preview_offline", False):
            return None, "Camera not streaming", 409
        meta = getattr(self, "preview_meta", None)
        if meta is None:
            return None, "No preview meta yet", 503
        return meta, None, 200

    def get_rtsp_url(self, camera_id: int):
        if getattr(self, "rtsp_missing", False):
            return None
        return getattr(self, "rtsp_url", None) or "rtsp://127.0.0.1/cam"


class FakeInference:
    def __init__(
        self,
        ready: bool = True,
        paused: bool = True,
        model_loaded: bool = True,
        load_error: Optional[str] = None,
    ) -> None:
        self.ready = ready
        self.paused = paused
        self.model_loaded = model_loaded
        self._load_error = load_error
        self.pause_calls = 0
        self.resume_calls = 0

    def is_ready(self) -> bool:
        return self.ready

    def pause(self) -> None:
        self.pause_calls += 1
        self.paused = True

    def resume(self) -> None:
        self.resume_calls += 1
        self.paused = False

    def is_paused(self) -> Optional[bool]:
        return self.paused

    def is_model_loaded(self) -> bool:
        return self.model_loaded

    def wait_model_ready(self, timeout: float) -> bool:
        return self.model_loaded

    def load_error(self) -> Optional[str]:
        return self._load_error


class FakeNodeStateStore:
    def __init__(self, ready: bool = True, validate_pairs=None) -> None:
        self._ready = ready
        self._ns = NodeState(validate_pairs or [])

    def is_ready(self) -> bool:
        return self._ready

    def update_detection(self, node_id: str, detected: bool) -> None:
        self._ns.get_state_nodes(node_id, detected)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._ns.points

    def toggle_flag(self, node_id: str) -> Optional[bool]:
        return self._ns.toggle_flag(node_id)

    def discard_from_ready(self, node_id: str) -> None:
        self._ns.discard_from_ready(node_id)

    def get_detected_start_nodes(self) -> Set[str]:
        return self._ns.get_detected_start_nodes()

    def snapshot_points(self) -> Dict[str, Dict[str, bool]]:
        return self._ns.snapshot_points()

    def apply_reset(self, order_id: str, status: int) -> ResetResult:
        return reset_flags_by_order(self._ns, order_id, status)

    def ready_starts(self) -> Set[str]:
        return set(self._ns.ready_start_list)

    def ready_ends(self) -> Set[str]:
        return set(self._ns.ready_end_list)

    def get_validate_pairs(self) -> Sequence:
        return self._ns.validate_pairs

    def set_pair_used(
        self, start_point: str, end_point: str, order_id: str, empty_car: bool = False
    ) -> None:
        self._ns.set_pair_used(start_point, end_point, order_id, empty_car=empty_car)

    def process_starts(self) -> None:
        self._ns.process_starts()

    def process_ends(self) -> None:
        self._ns.process_ends()


class FakeDispatchGateway:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.sent: List[Dict[str, Any]] = []

    def send(self, payload: Dict[str, Any]) -> bool:
        self.sent.append(payload)
        return self.ok


class FakeCameraConfigRepo:
    def __init__(self) -> None:
        self.items: Dict[int, Dict[str, Any]] = {}
        self._seq = 1

    async def get_all(self):
        return list(self.items.values())

    async def get_by_area(self, area: str):
        return [v for v in self.items.values() if v.get("zone_id") == area.upper()]

    async def create(self, doc):
        cid = doc.get("cameraId", self._seq)
        self._seq += 1
        self.items[cid] = doc
        return str(cid)

    async def update_by_camera_id(self, camera_id, data):
        if camera_id not in self.items:
            return False
        self.items[camera_id].update(data)
        return True

    async def delete_by_camera_id(self, camera_id):
        return self.items.pop(camera_id, None) is not None


class FakePairsRepo:
    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    async def get_by_zone(self, zone_id: str):
        return [r for r in self.rows if r.get("zone_id") == zone_id.upper()]

    async def set_enabled(self, start_point, end_point, enabled):
        for r in self.rows:
            if r["start_point"] == start_point and r.get("end_point") == end_point:
                r["enabled"] = enabled
                return True
        return False

    async def create(self, doc):
        self.rows.append(doc)
        return "pair-1"

    async def delete(self, start_point, end_point):
        before = len(self.rows)
        self.rows = [
            r
            for r in self.rows
            if not (r["start_point"] == start_point and r.get("end_point") == end_point)
        ]
        return len(self.rows) < before

    async def get_as_tuples(self):
        return [(r["start_point"], r.get("end_point")) for r in self.rows]


class FakeNodeRepo:
    def __init__(self) -> None:
        self.rows: Dict[str, Dict[str, Any]] = {}

    async def get_by_zone(self, zone_id: str):
        return [r for r in self.rows.values() if r.get("zone_id") == zone_id.upper()]

    async def get_by_id(self, node_id: str):
        return self.rows.get(node_id)

    async def get_by_camera(self, camera_id: int):
        return [r for r in self.rows.values() if r.get("camera_id") == camera_id]

    async def set_enabled(self, node_id: str, enabled: bool):
        if node_id not in self.rows:
            return False
        self.rows[node_id]["enabled"] = enabled
        return True

    async def set_camera_nodes_enabled(self, camera_id: int, enabled: bool):
        n = 0
        for r in self.rows.values():
            if r.get("camera_id") == camera_id:
                r["enabled"] = enabled
                n += 1
        return n

    async def update_priority(self, node_id: str, priority: int):
        if node_id not in self.rows:
            return False
        self.rows[node_id]["priority"] = priority
        return True

    async def create(self, doc):
        self.rows[doc["node_id"]] = doc
        return "nid-1"

    async def delete_by_node_id(self, node_id: str):
        return self.rows.pop(node_id, None) is not None


class FakeRuntimeControl:
    def __init__(self) -> None:
        self.running = False
        self.starts = 0
        self.stops = 0
        self.reloads = 0

    async def start(self):
        self.starts += 1
        self.running = True
        return self.status()

    def stop(self):
        self.stops += 1
        self.running = False
        return self.status()

    def status(self):
        return {"running": self.running, "cameras": {"total": 0, "enabled": 0, "alive": 0}}

    async def reload(self):
        self.reloads += 1
        self.running = True
        return self.status()

