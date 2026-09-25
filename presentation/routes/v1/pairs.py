"""Pair routes — `/api/v1/pairs/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from application.container import container
from domain.permissions import PAIR_READ, PAIR_WRITE
from presentation.deps import client_info, require_permission
from presentation.http_v1 import data_or_error
from presentation.schemas import (
    CreatePairPayload,
    DeletePairPayload,
    SetPairEnabledPayload,
    UpdatePairPayload,
)

router = APIRouter(prefix="/api/v1/pairs", tags=["pairs-v1"])


async def _audit(
    request: Request,
    user: Dict[str, Any],
    action: str,
    payload: Dict[str, Any],
    status: int,
) -> None:
    ip, _ = client_info(request)
    await container.action_audit.log(
        user=user.get("username") or user.get("user_id") or "",
        role=user.get("role") or "",
        action=action,
        endpoint=str(request.url.path),
        payload=payload,
        ip=ip,
        status=status,
    )


@router.get(
    "/get_pairs",
    summary="Danh sách pair — kèm isBlocked (enabled / node / bảo trì)",
)
async def get_pairs(
    zoneId: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(PAIR_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_node_pairs_v1.execute(zoneId))


@router.post(
    "/create_pair",
    summary="Tạo pair — validate node, trùng → 409, reload runtime",
)
async def create_pair(
    payload: CreatePairPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(PAIR_WRITE)),
) -> Dict[str, Any]:
    result = await container.create_pair_v1.execute(
        start_node_id=payload.startNodeId,
        zone_id=payload.zoneId,
        pair_type=payload.pairType,
        end_node_id=payload.endNodeId,
        enabled=payload.enabled,
        auto_dispatch=payload.autoDispatch,
        name=payload.name,
    )
    await _audit(
        request,
        user,
        "create_pair",
        payload.model_dump(),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.patch(
    "/update_pair",
    summary="Sửa start / end / zone / pairType / enabled / autoDispatch",
)
async def update_pair(
    payload: UpdatePairPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(PAIR_WRITE)),
) -> Dict[str, Any]:
    result = await container.update_pair_v1.execute(
        pair_id=payload.id,
        start_node_id=payload.startNodeId,
        end_node_id=payload.endNodeId,
        zone_id=payload.zoneId,
        pair_type=payload.pairType,
        enabled=payload.enabled,
        auto_dispatch=payload.autoDispatch,
        name=payload.name,
    )
    await _audit(
        request,
        user,
        "update_pair",
        payload.model_dump(exclude_none=True),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.post(
    "/delete_pair",
    summary="Xóa pair — reload runtime",
)
async def delete_pair(
    payload: DeletePairPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(PAIR_WRITE)),
) -> Dict[str, Any]:
    result = await container.delete_pair_v1.execute(
        pair_id=payload.id,
        start_node_id=payload.startNodeId,
        end_node_id=payload.endNodeId,
    )
    await _audit(
        request,
        user,
        "delete_pair",
        payload.model_dump(exclude_none=True),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.post(
    "/set_pair_enabled",
    summary="Bật/tắt pair — reload runtime",
)
async def set_pair_enabled(
    payload: SetPairEnabledPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(PAIR_WRITE)),
) -> Dict[str, Any]:
    result = await container.set_pair_enabled_v1.execute(
        enabled=payload.enabled,
        pair_id=payload.id,
        start_node_id=payload.startNodeId,
        end_node_id=payload.endNodeId,
    )
    await _audit(
        request,
        user,
        "set_pair_enabled",
        payload.model_dump(exclude_none=True),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)
