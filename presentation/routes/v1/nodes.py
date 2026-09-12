"""Node routes — `/api/v1/nodes/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from application.container import container
from domain.permissions import NODE_MAINTENANCE, NODE_READ
from presentation.deps import client_info, require_permission
from presentation.http_v1 import data_or_error
from presentation.schemas import SetLockPayload, SetMaintenancePayload, UnlockPayload

router = APIRouter(prefix="/api/v1/nodes", tags=["nodes-v1"])


@router.get(
    "/get_nodes",
    summary="Danh sách node — lọc tùy chọn theo zoneId",
)
async def get_nodes(
    zoneId: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(NODE_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_nodes_v1.execute(zoneId))


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
