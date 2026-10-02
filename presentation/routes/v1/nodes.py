"""Node routes — `/api/v1/nodes/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from application.container import container
from domain.permissions import CAMERA_WRITE, NODE_MAINTENANCE, NODE_READ
from presentation.deps import current_user, require_permission
from presentation.http_v1 import audited_or_error, data_or_error, system_audited_or_error
from presentation.openapi_responses import RUNTIME_STATE, UNLOCK_BY_SYSTEM
from presentation.schemas import (
    SetLockPayload,
    SetMaintenancePayload,
    UnlockBySystemPayload,
    UnlockByUserPayload,
    UpdateNodePayload,
)

router = APIRouter()


@router.get(
    "/get_runtime_state",
    summary="Snapshot runtime node (detected / isReady / lock) từ RAM",
    responses=RUNTIME_STATE,
)
def get_runtime_state(
    _user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    """
    Tất cả node trong RAM; FE tự filter theo zone/camera.
    Runtime chưa bind → `{ runtimeReady: false, items: [] }` (HTTP 200).
    """
    return data_or_error(container.get_node_runtime_state_v1.execute())


@router.get(
    "/get_nodes",
    summary="Danh sách node — lọc tùy chọn theo zoneId (mirror từ camera)",
)
async def get_nodes(
    zoneId: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(NODE_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_nodes_v1.execute(zoneId))


@router.patch(
    "/update_node",
    summary="Sửa priority / enabled (không đổi cameraId / zoneId)",
)
async def update_node(
    payload: UpdateNodePayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.update_node_v1.execute(
        payload.nodeId,
        priority=payload.priority,
        enabled=payload.enabled,
        zone_id=payload.zoneId,
        camera_id=payload.cameraId,
    )
    return await audited_or_error(
        result, request, user, "update_node", payload.model_dump(exclude_none=True)
    )


@router.post(
    "/set_maintenance",
    summary="Bật/tắt bảo trì node (khác với enabled; độc lập với lock)",
)
async def set_maintenance(
    payload: SetMaintenancePayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(NODE_MAINTENANCE)),
) -> Dict[str, Any]:
    result = await container.set_maintenance_v1.execute(
        payload.nodeId,
        payload.isUnderMaintenance,
        payload.maintenanceReason,
    )
    return await audited_or_error(
        result, request, user, "set_maintenance", payload.model_dump()
    )


@router.post(
    "/set_lock",
    summary="Operator bật user-lock trên node (Mongo field lock.user)",
)
async def set_lock(
    payload: SetLockPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(NODE_MAINTENANCE)),
) -> Dict[str, Any]:
    result = await container.set_lock_v1.execute(payload.nodeId, user=payload.user)
    return await audited_or_error(
        result, request, user, "set_lock", payload.model_dump()
    )


@router.post(
    "/unlock_by_user",
    summary="Operator gỡ lock.user + lock.system trên một node (JWT)",
)
async def unlock_by_user(
    payload: UnlockByUserPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(NODE_MAINTENANCE)),
) -> Dict[str, Any]:
    result = await container.unlock_v1.execute(payload.nodeId)
    return await audited_or_error(
        result, request, user, "unlock_by_user", payload.model_dump()
    )


@router.post(
    "/unlock_by_system",
    summary="Gỡ system lock theo orderId — webhook external / ICS (không Bearer)",
    responses=UNLOCK_BY_SYSTEM,
)
async def unlock_by_system(
    payload: UnlockBySystemPayload,
    request: Request,
) -> Dict[str, Any]:
    """ICS/AMR force-reset theo orderId — không JWT. Log → get_system_action_logs."""
    result = container.reset_flags.execute(payload.orderId, payload.status)
    return await system_audited_or_error(
        result,
        request,
        "unlock_by_system",
        payload.model_dump(),
        order_id=payload.orderId,
    )
