"""
Polling snapshot — một GET gộp trạng thái để FE poll + snapshot lúc vào app/reconnect.

Không thay SSE; giảm số round-trip so với gọi lần lượt get_cameras + get_zones + …
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, Set

from application.result import UseCaseResult


class _CamerasUC(Protocol):
    async def execute(self) -> UseCaseResult: ...


class _ZonesUC(Protocol):
    async def execute(self) -> UseCaseResult: ...


class _NotifStore(Protocol):
    async def count_unread(self, user_id: str) -> int: ...


class _MapState(Protocol):
    async def get_active_version_id(self) -> Optional[str]: ...


def compute_etag(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class GetPollSnapshot:
    """
    Trả trạng thái hiện tại (snapshot) cho chu kỳ poll.

    `include`: tập con cameras|zones|notifications|map — mặc định tất cả.
    """

    def __init__(
        self,
        get_cameras: _CamerasUC,
        get_zones: _ZonesUC,
        notifications: _NotifStore,
        map_state: _MapState,
        recommended_interval_sec: float = 3.0,
    ) -> None:
        self._cameras = get_cameras
        self._zones = get_zones
        self._notifications = notifications
        self._map_state = map_state
        self._interval = recommended_interval_sec

    async def execute(
        self,
        user_id: str,
        *,
        include: Optional[Set[str]] = None,
    ) -> UseCaseResult:
        parts = include or {"cameras", "zones", "notifications", "map"}
        body: Dict[str, Any] = {
            "serverTime": datetime.now(timezone.utc).isoformat(),
            "pollIntervalSec": self._interval,
        }

        if "cameras" in parts:
            cam = await self._cameras.execute()
            items = []
            if cam.success:
                for row in cam.data.get("items") or []:
                    items.append(
                        {
                            "cameraId": row.get("cameraId"),
                            "status": row.get("status"),
                            "enabled": row.get("enabled"),
                            "zone": row.get("zone"),
                            "error": row.get("error"),
                        }
                    )
            body["cameras"] = {"items": items}

        if "zones" in parts:
            zones = await self._zones.execute()
            items = []
            if zones.success:
                for row in zones.data.get("items") or []:
                    items.append(
                        {
                            "id": row.get("id"),
                            "isRunning": row.get("isRunning"),
                            "isConfigEnabled": row.get("isConfigEnabled"),
                            "cameraCount": row.get("cameraCount"),
                            "nodeCount": row.get("nodeCount"),
                        }
                    )
            body["zones"] = {"items": items}

        if "notifications" in parts:
            unread = await self._notifications.count_unread(user_id)
            body["notifications"] = {"unreadCount": int(unread)}

        if "map" in parts:
            active = await self._map_state.get_active_version_id()
            body["map"] = {"activeVersionId": active}

        # ETag không gồm serverTime / pollIntervalSec (đổi mỗi lần → vô dụng)
        stable = {k: v for k, v in body.items() if k not in ("serverTime", "pollIntervalSec")}
        etag = compute_etag(stable)
        body["etag"] = etag
        return UseCaseResult.ok(**body)
