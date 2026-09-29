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
from presentation.openapi_responses import CONFIRM_READY, SSE_EVENTS

router = APIRouter()

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
    responses=CONFIRM_READY,
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
    responses=SSE_EVENTS,
)
async def runtime_events(
    _user: Dict[str, Any] = Depends(current_user_sse),
) -> StreamingResponse:
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
