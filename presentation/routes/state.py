"""State routes ngoài `/api/v1` — chỉ webhook ICS (GIỮ_ICS)."""
from typing import Any, Dict

from fastapi import APIRouter

from application.container import container
from presentation.http import to_http
from presentation.schemas import WebhookPayload

router = APIRouter(tags=["state"])


@router.post("/delete-flag")
async def delete_flag(payload: WebhookPayload) -> Dict[str, Any]:
    """Webhook ICS — gỡ system lock theo orderId (RAM + Mongo)."""
    return to_http(container.reset_flags.execute(payload.orderId, payload.status))
