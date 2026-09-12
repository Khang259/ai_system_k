"""Notification repository — collection: notifications."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.persistence.base_repository import BaseRepository, _now


class NotificationRepository(BaseRepository):
    def __init__(self):
        super().__init__("notifications")

    async def create(
        self,
        *,
        title: str,
        message: str,
        type: str = "info",
        user_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        snapshot_file: Optional[str] = None,
    ) -> str:
        return await self.insert_one(
            {
                "title": title,
                "message": message,
                "type": type,
                "user_id": user_id,
                "meta": meta or {},
                "snapshot_file": snapshot_file,
                "read_at": None,
            }
        )

    async def list_for_user(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict], int]:
        # Bản ghi của user hoặc broadcast (user_id null)
        query: Dict[str, Any] = {
            "$or": [{"user_id": user_id}, {"user_id": None}],
        }
        if unread_only:
            query["read_at"] = None
        return await self.find_page(
            query, page=page, page_size=page_size, sort=[("created_at", -1)]
        )

    async def mark_read(self, notification_id: str, user_id: str) -> bool:
        from bson import ObjectId

        try:
            oid = ObjectId(notification_id)
        except Exception:
            return False
        result = await self._col().update_one(
            {
                "_id": oid,
                "$or": [{"user_id": user_id}, {"user_id": None}],
                "read_at": None,
            },
            {"$set": {"read_at": _now(), "updated_at": _now()}},
        )
        return result.modified_count > 0 or result.matched_count > 0

    async def mark_all_read(self, user_id: str) -> int:
        result = await self._col().update_many(
            {
                "$or": [{"user_id": user_id}, {"user_id": None}],
                "read_at": None,
            },
            {"$set": {"read_at": _now(), "updated_at": _now()}},
        )
        return int(result.modified_count)

    async def count_unread(self, user_id: str) -> int:
        return await self.count(
            {
                "$or": [{"user_id": user_id}, {"user_id": None}],
                "read_at": None,
            }
        )


notification_repository = NotificationRepository()
