"""Node routes — `/api/v1/nodes/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from application.container import container
from domain.permissions import CAMERA_WRITE, NODE_MAINTENANCE, NODE_READ
from presentation.deps import client_info, current_user, require_permission
from presentation.http_v1 import data_or_error
from presentation.schemas import (
    DeleteNodePayload,
    SetLockPayload,
    SetMaintenancePayload,
    UnlockByOrderPayload,
    UnlockPayload,
    UpdateNodePayload,
)

router = APIRouter(prefix="/api/v1/nodes", tags=["nodes-v1"])


@router.get(
    "/get_runtime_state",
    summary="Snapshot runtime node (detected / isReady / lock) từ RAM",
    responses={
        200: {"description": "runtimeReady + items (rỗng nếu runtime chưa sẵn — không 500)"},
        401: {"description": "Thiếu / sai token"},
    },
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
    summary="Danh sách node — lọc tùy chọn theo zoneId",
)
async def get_nodes(
    zoneId: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(NODE_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_nodes_v1.execute(zoneId))


@router.patch(
    "/update_node",
    summary="Sửa priority / enabled / zoneId (không đổi cameraId)",
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
    ip, _ = client_info(request)
    await container.action_audit.log(
        user=user.get("username") or "",
        role=user.get("role") or "",
        action="update_node",
        endpoint=str(request.url.path),
        payload=payload.model_dump(exclude_none=True),
        ip=ip,
        status=200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.post(
    "/delete_node",
    summary="Xóa node + cascade pair + ROI (cần inference pause)",
)
async def delete_node(
    payload: DeleteNodePayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.delete_node_v1.execute(payload.nodeId)
    ip, _ = client_info(request)
    await container.action_audit.log(
        user=user.get("username") or "",
        role=user.get("role") or "",
        action="delete_node",
        endpoint=str(request.url.path),
        payload=payload.model_dump(),
        ip=ip,
        status=200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


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
    ip, _ = client_info(request)
    await container.action_audit.log(
        user=user.get("username") or "",
        role=user.get("role") or "",
        action="set_maintenance",
        endpoint=str(request.url.path),
        payload=payload.model_dump(),
        ip=ip,
        status=200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


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
    ip, _ = client_info(request)
    await container.action_audit.log(
        user=user.get("username") or "",
        role=user.get("role") or "",
        action="set_lock",
        endpoint=str(request.url.path),
        payload=payload.model_dump(),
        ip=ip,
        status=200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.post(
    "/unlock",
    summary="Gỡ user và/hoặc system lock trên node",
)
async def unlock(
    payload: UnlockPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(NODE_MAINTENANCE)),
) -> Dict[str, Any]:
    result = await container.unlock_v1.execute(
        payload.nodeId, user=payload.user, system=payload.system
    )
    ip, _ = client_info(request)
    await container.action_audit.log(
        user=user.get("username") or "",
        role=user.get("role") or "",
        action="unlock",
        endpoint=str(request.url.path),
        payload=payload.model_dump(),
        ip=ip,
        status=200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.post(
    "/unlock_by_order",
    summary="Gỡ system lock theo orderId — webhook external / ICS (không Bearer)",
    responses={
        200: {"description": "Đã reset theo status 3|23"},
        400: {"description": "orderId không tìm thấy / status không hợp lệ / runtime chưa sẵn"},
    },
)
async def unlock_by_order(
    payload: UnlockByOrderPayload,
    request: Request,
) -> Dict[str, Any]:
    """
    Server ngoài (ICS/AMR) force-reset lệnh theo orderId — không JWT.
    Cùng policy webhook POST /delete-flag (ResetFlagsByOrder).
    """
    result = container.reset_flags.execute(payload.orderId, payload.status)
    ip, _ = client_info(request)
    await container.action_audit.log(
        user="external",
        role="",
        action="unlock_by_order",
        endpoint=str(request.url.path),
        payload=payload.model_dump(),
        ip=ip,
        status=200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)
