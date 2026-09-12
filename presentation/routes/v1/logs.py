"""Logs routes — `/api/v1/logs/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from application.container import container
from domain.permissions import LOGS_READ
from presentation.deps import require_permission
from presentation.http_v1 import data_or_error

router = APIRouter(prefix="/api/v1/logs", tags=["logs-v1"])


@router.get("/get_audit_logs", summary="Nhật ký đăng nhập / sự kiện auth")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(LOGS_READ)),
) -> Dict[str, Any]:
    return data_or_error(
        await container.get_audit_logs_v1.execute(
            page=page, page_size=pageSize, from_iso=from_, to_iso=to
        )
    )


@router.get("/get_user_action_logs", summary="Thao tác người dùng (ROI, maintenance…)")
async def get_user_action_logs(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(LOGS_READ)),
) -> Dict[str, Any]:
    return data_or_error(
        await container.get_user_action_logs_v1.execute(
            page=page, page_size=pageSize, from_iso=from_, to_iso=to
        )
    )


@router.get(
    "/get_system_action_logs",
    summary="Nhật ký hệ thống — chủ yếu dispatch ICS",
)
async def get_system_action_logs(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(LOGS_READ)),
) -> Dict[str, Any]:
    return data_or_error(
        await container.get_system_action_logs_v1.execute(
            page=page, page_size=pageSize, from_iso=from_, to_iso=to
        )
    )
