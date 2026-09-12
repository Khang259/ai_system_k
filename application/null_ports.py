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

    def set_camera_enabled_by_id(self, camera_id: int, on: bool) -> bool:
        return False

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

    def discard_from_ready(self, node_id: str) -> None:
        return None

    def get_detected_start_nodes(self) -> Set[str]:
        return set()

    def snapshot_points(self) -> Dict[str, Dict[str, Any]]:
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

    def apply_persisted_lock(self, node_id, *, user=False, system=False, order_id=None):
        return None

    def clear_system_by_order_id(self, order_id: str):
        return []

    def lock_view(self, node_id: str):
        return {"user": False, "system": False, "orderId": None}

class NullDispatchGateway:
    def send(self, payload: Dict[str, Any]) -> bool:
        return False


class NullDbHealth:
    async def ping(self) -> bool:
        return False


class NullWebrtcRunner:
    def status(self) -> Dict[str, Any]:
        return {"alive": False, "owned": False, "watchdog": False}


class NullUserRepo:
    async def get_by_username(self, username):
        return None

    async def get_by_id(self, user_id):
        return None


class NullRefreshTokenStore:
    async def save(self, user_id, token_hash, expires_at):
        return None

    async def find(self, token_hash):
        return None

    async def revoke_user(self, user_id):
        return None


class NullAuthAudit:
    async def log_event(self, username, event, ip, user_agent=""):
        return None

    async def count_recent_failures(self, username, minutes):
        return 0


class NullActionAudit:
    async def log(self, user, role, action, endpoint, payload, ip, status):
        return None


class NullPasswordHasher:
    """Chưa bind auth → mọi lần verify đều thất bại (mặc định an toàn)."""

    def hash(self, password: str) -> str:
        return ""

    def verify(self, password: str, hashed: str) -> bool:
        return False

    def dummy_hash(self) -> str:
        return ""


class NullTokenIssuer:
    def issue_access(self, user):
        return {"token": "", "expires_in": 0}

    def decode_access(self, token):
        return None

    def new_refresh(self):
        return {"raw": "", "hash": "", "expires_at": None}

    def hash_refresh(self, raw: str) -> str:
        return ""


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

    async def get_by_id(self, camera_id):
        return None

    async def create(self, doc):
        return ""

    async def update_by_camera_id(self, camera_id, data):
        return False

    async def delete_by_camera_id(self, camera_id):
        return False

    async def set_enabled(self, camera_id, enabled):
        return False

    async def upsert_roi(self, camera_id, node_id, roi_doc):
        return False

    async def delete_roi(self, camera_id, node_id):
        return False


class NullPairsRepo:
    async def get_by_zone(self, zone_id):
        return []

    async def list_all(self):
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
    async def get_all(self):
        return []

    async def get_by_zone(self, zone_id):
        return []

    async def get_by_id(self, node_id):
        return None

    async def get_by_camera(self, camera_id):
        return []

    async def set_enabled(self, node_id, enabled):
        return False

    async def set_maintenance(self, node_id, under, reason):
        return False

    async def set_lock(self, node_id, *, user=None, system=None, order_id=None):
        return False

    async def clear_system_lock_by_order(self, order_id):
        return []

    async def list_with_lock(self):
        return []

    async def set_camera_nodes_enabled(self, camera_id, enabled):
        return 0

    async def update_priority(self, node_id, priority):
        return False

    async def create(self, doc):
        return ""

    async def delete_by_node_id(self, node_id):
        return False


class NullZoneRepo:
    async def get_all(self):
        return []


class NullPagedLogStore:
    async def find_page(self, query, page=1, page_size=20, sort=None):
        return [], 0


class NullNotificationStore:
    async def create(
        self,
        *,
        title,
        message,
        type="info",
        user_id=None,
        meta=None,
        snapshot_file=None,
    ):
        return "null"

    async def list_for_user(self, user_id, *, unread_only=False, page=1, page_size=20):
        return [], 0

    async def mark_read(self, notification_id, user_id):
        return False

    async def mark_all_read(self, user_id):
        return 0

    async def count_unread(self, user_id):
        return 0


class NullMapVersionStore:
    def __init__(self):
        self.rows = []

    async def insert_version(self, doc):
        self.rows.append(dict(doc))
        return "ok"

    async def get_by_version_id(self, version_id):
        for r in self.rows:
            if r.get("version_id") == version_id:
                return dict(r)
        return None

    async def list_newest_first(self):
        return list(reversed(self.rows))

    async def list_oldest_first(self):
        return list(self.rows)

    async def delete_by_version_id(self, version_id):
        before = len(self.rows)
        self.rows = [r for r in self.rows if r.get("version_id") != version_id]
        return len(self.rows) < before

    async def count_all(self):
        return len(self.rows)


class NullMapStateStore:
    def __init__(self):
        self.active = None

    async def get_active_version_id(self):
        return self.active

    async def set_active_version_id(self, version_id):
        self.active = version_id

