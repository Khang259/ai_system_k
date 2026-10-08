"""Dispatch routes — `/api/v1/dispatch/*` (panel order đang chạy + SSE)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from application.container import container
from presentation.deps import current_user, current_user_sse
from presentation.http_v1 import data_or_error
from presentation.openapi_responses import ACTIVE_TASKS, SSE_EVENTS
from presentation.sse import sse_response

router = APIRouter()


@router.get(
    "/get_active_tasks",
    summary="Order đang chạy từ ICS getOrderList (dùng sau restart / mở app)",
    responses=ACTIVE_TASKS,
)
async def get_active_tasks(
    _user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    return data_or_error(await container.get_active_tasks_v1.execute())


@router.get(
    "/events",
    summary="SSE dispatch.task (upsert theo orderId) / dispatch.task.removed",
    responses=SSE_EVENTS,
)
async def dispatch_events(
    _user: Dict[str, Any] = Depends(current_user_sse),
) -> StreamingResponse:
    return sse_response(container.active_task_hub, lambda event: event)
