"""Polling — `/api/v1/poll/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, Depends, Header, Query, Response

from application.container import container
from presentation.deps import current_user
from presentation.http_v1 import data_or_error

router = APIRouter(prefix="/api/v1/poll", tags=["poll-v1"])


def _parse_include(raw: Optional[str]) -> Optional[Set[str]]:
    if not raw or not raw.strip():
        return None
    allowed = {"cameras", "zones", "notifications", "map"}
    parts = {p.strip() for p in raw.split(",") if p.strip()}
    return parts & allowed or None


@router.get(
    "/get_snapshot",
    summary="Snapshot trạng thái để FE poll / tải lại khi vào app hoặc reconnect",
    responses={
        200: {"description": "Trạng thái hiện tại + etag + pollIntervalSec"},
        304: {"description": "Không đổi so với If-None-Match"},
    },
)
async def get_snapshot(
    response: Response,
    include: Optional[str] = Query(
        None,
        description="cameras,zones,notifications,map — bỏ trống = tất cả",
    ),
    if_none_match: Optional[str] = Header(None, alias="If-None-Match"),
    user: Dict[str, Any] = Depends(current_user),
):
    """
    Pattern FE:
    1) Vào app / focus lại → gọi ngay (snapshot).
    2) Poll theo `pollIntervalSec` (gợi ý ~3s).
    3) Gửi `If-None-Match: <etag>` → 304 nếu không đổi (tiết kiệm JSON).
    """
    result = await container.get_poll_snapshot_v1.execute(
        user["user_id"],
        include=_parse_include(include),
    )
    data = data_or_error(result)
    etag = data.get("etag") or ""
    client_tag = (if_none_match or "").strip().strip('"')
    if client_tag and etag and client_tag == etag:
        return Response(status_code=304)
    response.headers["ETag"] = f'"{etag}"'
    response.headers["Cache-Control"] = "no-store"
    return data
