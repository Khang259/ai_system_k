"""Dispatch / pairs routes — `/api/v1/dispatch/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from application.container import container
from domain.permissions import NODE_READ
from presentation.deps import require_permission
from presentation.http_v1 import data_or_error

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch-v1"])


@router.get(
    "/get_node_pairs",
    summary="Danh sách cặp node — kèm isBlocked tính từ enabled/maintenance",
)
async def get_node_pairs(
    zoneId: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(NODE_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_node_pairs_v1.execute(zoneId))
