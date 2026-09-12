"""System routes — `/api/v1/system/*`."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from application.container import container
from domain.permissions import SYSTEM_CONTROL
from presentation.deps import current_user, require_permission
from presentation.http_v1 import data_or_error

router = APIRouter(prefix="/api/v1/system", tags=["system-v1"])


@router.get(
    "/get_health",
    summary="Health Mongo + runtime (+ MediaMTX report) — alias chuẩn /api/v1 của GET /health",
    responses={
        200: {"description": "status=ok"},
        503: {"description": "status=degraded — vẫn trả mongo/runtime/webrtc trong body"},
    },
)
async def get_health(
    _user: Dict[str, Any] = Depends(current_user),
):
    """
    Cần Bearer (cùng nhóm /api/v1). Body luôn có field health; lỗi = HTTP 503 + message.
    """
    result = await container.get_health.execute()
    if result.success:
        return result.data
    body = dict(result.data)
    body["message"] = result.error or "degraded"
    return JSONResponse(status_code=503, content=body)


@router.post(
    "/start_all",
    summary="Bật mọi camera — alias của POST /cameras/start-all",
    responses={
        401: {"description": "Thiếu / sai token"},
        403: {"description": "Thiếu system.control (thường chỉ admin)"},
        503: {"description": "Runtime / model chưa sẵn sàng, hoặc không camera nào streaming"},
    },
)
async def start_all(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(
        await container.start_all_cameras.execute(),
        fail_status=503,
    )


@router.post(
    "/stop_all",
    summary="Tắt mọi camera — alias của POST /cameras/stop-all",
    responses={
        401: {"description": "Thiếu / sai token"},
        403: {"description": "Thiếu system.control (thường chỉ admin)"},
        503: {"description": "Runtime chưa khởi động"},
    },
)
def stop_all(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(
        container.stop_all_cameras.execute(),
        fail_status=503,
    )
