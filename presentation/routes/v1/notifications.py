"""Notification routes — `/api/v1/notifications/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from application.container import container
from domain.permissions import LOGS_READ
from presentation.deps import current_user, require_permission
from presentation.http_v1 import data_or_error

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications-v1"])


class MarkReadPayload(BaseModel):
    id: str


@router.get(
    "/get_notifications",
    summary="Thông báo của user hiện tại (+ broadcast)",
)
async def get_notifications(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    unreadOnly: bool = Query(False),
    user: Dict[str, Any] = Depends(require_permission(LOGS_READ)),
) -> Dict[str, Any]:
    # Dùng logs.read tạm — viewer/operator đều xem được chuông thông báo
    return data_or_error(
        await container.get_notifications_v1.execute(
            user["user_id"],
            unread_only=unreadOnly,
            page=page,
            page_size=pageSize,
        )
    )


@router.post("/mark_read", summary="Đánh dấu một thông báo đã đọc")
async def mark_read(
    payload: MarkReadPayload,
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    return data_or_error(
        await container.mark_notification_read_v1.execute(payload.id, user["user_id"])
    )


@router.post("/mark_all_read", summary="Đánh dấu tất cả thông báo đã đọc")
async def mark_all_read(
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    return data_or_error(
        await container.mark_all_notifications_read_v1.execute(user["user_id"])
    )
