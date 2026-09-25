"""Runtime routes — `/api/v1/runtime/*` (+ SSE node.runtime)."""
from __future__ import annotations

import asyncio
import json
import queue
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from application.container import container
from domain.permissions import SYSTEM_CONTROL
from presentation.deps import current_user, current_user_sse, require_permission
from presentation.http_v1 import data_or_error

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime-v1"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get(
    "/get_status",
    summary="Trạng thái runtime",
)
def get_status(
    _user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    return data_or_error(container.get_runtime_status.execute())


@router.post(
    "/reload",
    summary="Reload runtime (pairs/cameras)",
)
async def reload_runtime(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(
        await container.reload_runtime.execute(),
        fail_status=503,
    )


@router.post(
    "/confirm-ready",
    summary="Bật inference / bắt đầu scan",
    responses={
        401: {"description": "Thiếu / sai token"},
        403: {"description": "Thiếu system.control"},
        400: {"description": "Runtime chưa sẵn sàng / chưa start camera"},
    },
)
def confirm_ready(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(container.confirm_ready.execute())


@router.post(
    "/pause-scan",
    summary="Tắt inference (pause)",
)
def pause_scan(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(container.pause_scan.execute())


@router.get(
    "/events",
    summary="SSE runtime node — event node.runtime (detected / isReady / lock)",
    responses={
        200: {"description": "text/event-stream"},
        401: {"description": "Thiếu / sai token (header Bearer hoặc ?access_token=)"},
    },
)
async def runtime_events(
    _user: Dict[str, Any] = Depends(current_user_sse),
) -> StreamingResponse:
    """
    FE: snapshot trước (GET get_runtime_state / poll include=nodes), rồi mở EventSource.
    Auth EventSource: `?access_token=<jwt>` (trình duyệt không gửi Authorization).
    Heartbeat: event `ping` mỗi ~15s khi không có delta.
    """
    hub = container.runtime_state_hub

    async def _stream() -> AsyncIterator[str]:
        q = hub.subscribe()
        try:
            while True:
                try:
                    item = await asyncio.to_thread(q.get, True, 15.0)
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
                    continue
                payload = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                yield f"event: node.runtime\ndata: {payload}\n\n"
        finally:
            hub.unsubscribe(q)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
