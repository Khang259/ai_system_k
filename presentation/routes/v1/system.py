"""System routes — `/api/v1/system/*`."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from application.container import container
from domain.permissions import SYSTEM_CONTROL
from presentation.deps import current_user, require_permission
from presentation.http_v1 import data_or_error
from presentation.openapi_responses import (
    HEALTH,
    SYSTEM_START_ALL,
    SYSTEM_STOP_ALL,
)

router = APIRouter()

_DEPRECATE_START_ALL = {
    "X-Deprecated": "true",
    "X-Use-Instead": "/api/v1/system/start-cameras",
}


@router.get(
    "/get_health",
    summary="Health Mongo + runtime (+ MediaMTX report)",
    responses=HEALTH,
)
async def get_health(
    _user: Dict[str, Any] = Depends(current_user),
):
    result = await container.get_health.execute()
    if result.success:
        return result.data
    body = dict(result.data)
    body["message"] = result.error or "degraded"
    return JSONResponse(status_code=503, content=body)


@router.post(
    "/start-cameras",
    summary="Bật mọi camera + tự bật inference (scan)",
    responses=SYSTEM_START_ALL,
)
async def start_cameras(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(
        await container.start_cameras.execute(),
        fail_status=503,
    )


@router.post(
    "/start_all",
    summary="[Deprecated] Bật mọi camera — dùng /start-cameras",
    responses=SYSTEM_START_ALL,
    deprecated=True,
)
async def start_all(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> JSONResponse:
    """Giữ hành vi cũ (không auto-scan)."""
    data = data_or_error(
        await container.start_all_cameras.execute(),
        fail_status=503,
    )
    return JSONResponse(content=data, headers=_DEPRECATE_START_ALL)


@router.post(
    "/stop_all",
    summary="Tắt mọi camera",
    responses=SYSTEM_STOP_ALL,
)
def stop_all(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(
        container.stop_all_cameras.execute(),
        fail_status=503,
    )
