"""Snapshot image routes — `/api/v1/snapshots/*`."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from application.container import container
from domain.permissions import LOGS_READ
from presentation.deps import require_permission
from presentation.http_v1 import jpeg_or_error

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots-v1"])


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
