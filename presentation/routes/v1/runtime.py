"""Runtime routes — `/api/v1/runtime/*` (+ SSE node.runtime)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from application.container import container
from domain.permissions import SYSTEM_CONTROL
from presentation.deps import current_user, current_user_sse, require_permission
from presentation.http_v1 import data_or_error
from presentation.openapi_responses import (
    CANCEL_BATCH,
    CONFIRM_DISPATCH,
    PENDING_PAIRS,
    SSE_EVENTS,
    START_SCAN,
)
from presentation.sse import sse_response

router = APIRouter()


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
    "/start-scan",
    summary="Bật inference (detect) — chưa gửi ICS",
    responses=START_SCAN,
)
def start_scan(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(container.start_scan.execute())


@router.post(
    "/confirm-dispatch",
    summary="Xác nhận batch start isReady → mở cổng gửi ICS",
    responses=CONFIRM_DISPATCH,
)
def confirm_dispatch(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(container.confirm_dispatch.execute())


@router.get(
    "/get_pending_pairs",
    summary="Xem trước batch / start ready / cặp sẽ gửi",
    responses=PENDING_PAIRS,
)
def get_pending_pairs(
    _user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    return data_or_error(container.get_pending_pairs.execute())


@router.post(
    "/cancel-batch",
    summary="Huỷ batch đang mở — inference vẫn chạy",
    responses=CANCEL_BATCH,
)
def cancel_batch(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    return data_or_error(container.cancel_batch.execute())


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
    return sse_response(container.runtime_state_hub, lambda item: ("node.runtime", item))
