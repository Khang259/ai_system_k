"""Snapshot image routes — `/api/v1/snapshots/*`."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from application.container import container
from domain.permissions import LOGS_READ
from presentation.deps import require_permission
from presentation.http_v1 import data_or_error, jpeg_or_error

router = APIRouter()


@router.get(
    "/get_image",
    response_class=Response,
    summary="JPEG snapshot theo tên file (có Bearer) — 404 nếu đã dọn/hết hạn",
)
def get_image(
    file: str = Query(..., description="Chỉ tên file trong SNAPSHOT_DIR"),
    _user: Dict[str, Any] = Depends(require_permission(LOGS_READ)),
) -> Response:
    result = container.get_snapshot_image_v1.execute(file)
    if result.success:
        media = result.data.get("media_type") or "image/jpeg"
        return Response(content=result.data["jpeg"], media_type=media)
    return jpeg_or_error(result)


@router.get(
    "/get_by_order",
    summary="Meta snapshot theo orderId (Mongo) — dùng imageUrl → get_image",
)
async def get_by_order(
    orderId: str = Query(..., description="orderId lệnh ICS (vd S-start-end-…)"),
    _user: Dict[str, Any] = Depends(require_permission(LOGS_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_snapshots_by_order_v1.execute(orderId))
