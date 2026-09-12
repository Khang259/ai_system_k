"""Logs + notifications + snapshot file use cases cho /api/v1 đợt 4."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from application.fe_api.log_mappers import (
    map_audit,
    map_dispatch,
    map_notification,
    map_user_action,
    parse_iso,
)
from application.result import UseCaseResult


class PagedLogStore(Protocol):
    async def find_page(
        self, query: Dict, page: int = 1, page_size: int = 20, sort=None
    ): ...


class NotificationStore(Protocol):
    async def list_for_user(
        self, user_id: str, *, unread_only: bool = False, page: int = 1, page_size: int = 20
    ): ...

    async def mark_read(self, notification_id: str, user_id: str) -> bool: ...

    async def mark_all_read(self, user_id: str) -> int: ...


def _paged(items, total: int, page: int, page_size: int) -> Dict[str, Any]:
    return {"items": items, "total": total, "page": page, "pageSize": page_size}

def _time_query(
    field: str, from_iso: Optional[str], to_iso: Optional[str]
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    start = parse_iso(from_iso)
    end = parse_iso(to_iso)
    if start or end:
        rng: Dict[str, Any] = {}
        if start:
            rng["$gte"] = start
        if end:
            rng["$lte"] = end
        q[field] = rng
    return q


class GetAuditLogs:
    def __init__(self, store: PagedLogStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
    ) -> UseCaseResult:
        query = _time_query("created_at", from_iso, to_iso)
        items, total = await self._store.find_page(
            query, page=page, page_size=page_size, sort=[("created_at", -1)]
        )
        return UseCaseResult.ok(
            **_paged([map_audit(d) for d in items], total, page, page_size)
        )


class GetUserActionLogs:
    def __init__(self, store: PagedLogStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
    ) -> UseCaseResult:
        query: Dict[str, Any] = {"source": "user"}
        query.update(_time_query("created_at", from_iso, to_iso))
        items, total = await self._store.find_page(
            query, page=page, page_size=page_size, sort=[("created_at", -1)]
        )
        return UseCaseResult.ok(
            **_paged([map_user_action(d) for d in items], total, page, page_size)
        )


class GetSystemActionLogs:
    """Ưu tiên `dispatch_logs` — gần với tiến trình ICS / lệnh hệ thống."""

    def __init__(self, store: PagedLogStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
    ) -> UseCaseResult:
        query = _time_query("dispatched_at", from_iso, to_iso)
        # Bản ghi cũ có thể chỉ có created_at
        if not query:
            query = {}
        items, total = await self._store.find_page(
            query,
            page=page,
            page_size=page_size,
            sort=[("dispatched_at", -1), ("created_at", -1)],
        )
        return UseCaseResult.ok(
            **_paged([map_dispatch(d) for d in items], total, page, page_size)
        )


class GetNotifications:
    def __init__(self, store: NotificationStore) -> None:
        self._store = store

    async def execute(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> UseCaseResult:
        items, total = await self._store.list_for_user(
            user_id, unread_only=unread_only, page=page, page_size=page_size
        )
        return UseCaseResult.ok(
            **_paged([map_notification(d) for d in items], total, page, page_size)
        )


class MarkNotificationRead:
    def __init__(self, store: NotificationStore) -> None:
        self._store = store

    async def execute(self, notification_id: str, user_id: str) -> UseCaseResult:
        ok = await self._store.mark_read(notification_id, user_id)
        if not ok:
            return UseCaseResult.fail("Notification not found", http_status=404)
        return UseCaseResult.ok(id=notification_id, read=True)


class MarkAllNotificationsRead:
    def __init__(self, store: NotificationStore) -> None:
        self._store = store

    async def execute(self, user_id: str) -> UseCaseResult:
        n = await self._store.mark_all_read(user_id)
        return UseCaseResult.ok(updated=n)


class GetSnapshotImage:
    """Đọc JPEG trong SNAPSHOT_DIR — chỉ tên file, không path tuyệt đối."""

    def __init__(self, snapshot_dir: str) -> None:
        self._root = Path(snapshot_dir).resolve()

    def execute(self, filename: str) -> UseCaseResult:
        name = (filename or "").replace("\\", "/").split("/")[-1]
        if not name or name in (".", "..") or ".." in name:
            return UseCaseResult.fail("Tên file không hợp lệ", http_status=400)
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            return UseCaseResult.fail("Chỉ hỗ trợ ảnh JPEG/PNG", http_status=400)

        path = (self._root / name).resolve()
        try:
            path.relative_to(self._root)
        except ValueError:
            return UseCaseResult.fail("Đường dẫn không hợp lệ", http_status=400)

        if not path.is_file():
            # FE hiện "ảnh đã hết hạn" khi 404
            return UseCaseResult.fail("Snapshot không tồn tại hoặc đã hết hạn", http_status=404)

        data = path.read_bytes()
        media = "image/png" if name.lower().endswith(".png") else "image/jpeg"
        return UseCaseResult.ok(jpeg=data, media_type=media)
