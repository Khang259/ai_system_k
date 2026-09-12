"""Zone routes — `/api/v1/zones/*`."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from application.container import container
from domain.permissions import CAMERA_READ, ZONE_CONTROL
from presentation.deps import require_permission
from presentation.http_v1 import data_or_error
from presentation.schemas import ZoneControlPayload

router = APIRouter(prefix="/api/v1/zones", tags=["zones-v1"])


@router.get(
    "/get_zones",
    summary="Danh sách zone + isRunning (RAM) / isConfigEnabled (Mongo)",
)
async def get_zones(
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_zones_v1.execute())


@router.post(
    "/start_zone",
    summary="Bật camera thuộc zone (RAM) — alias của POST /cameras/{zone}/start-all",
    responses={
        401: {"description": "Thiếu / sai token"},
        403: {"description": "Thiếu zone.control"},
        503: {"description": "Runtime chưa khởi động"},
    },
)
def start_zone(
    payload: ZoneControlPayload,
    _user: Dict[str, Any] = Depends(require_permission(ZONE_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(
        container.start_zone_cameras.execute(payload.zoneId),
        fail_status=503,
    )


@router.post(
    "/stop_zone",
    summary="Tắt camera thuộc zone (RAM) — alias của POST /cameras/{zone}/stop-all",
    responses={
        401: {"description": "Thiếu / sai token"},
        403: {"description": "Thiếu zone.control"},
        503: {"description": "Runtime chưa khởi động"},
    },
)
def stop_zone(
    payload: ZoneControlPayload,
    _user: Dict[str, Any] = Depends(require_permission(ZONE_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(
        container.stop_zone_cameras.execute(payload.zoneId),
        fail_status=503,
    )
