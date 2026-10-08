"""External server webhooks — `/api/v1/external_server/*` (không Bearer)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request

from application.container import container
from presentation.http_v1 import system_audited_or_error
from presentation.openapi_responses import UNLOCK_BY_ORDER_STATUS
from presentation.schemas import OrderStatusWebhookPayload

router = APIRouter()


@router.post(
    "/unlock_by_order_status",
    summary="Webhook task status ICS theo orderId (6 → inprogress, 3|23 → gỡ lock)",
    responses=UNLOCK_BY_ORDER_STATUS,
)
async def unlock_by_order_status(
    body: OrderStatusWebhookPayload,
    request: Request,
) -> Dict[str, Any]:
    order_id = body.orderId
    result = await container.unlock_by_order_status_v1.execute(order_id, body.status)
    return await system_audited_or_error(
        result,
        request,
        "unlock_by_order_status",
        body.model_dump(),
        order_id=order_id,
    )
