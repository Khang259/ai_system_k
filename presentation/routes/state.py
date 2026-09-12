"""State and detection routes."""
from typing import Any, Dict
from fastapi import APIRouter

from presentation.schemas import DetectionPayload, WebhookPayload
from application.container import container
from presentation.http import to_http

router = APIRouter(tags=["state"])


@router.post("/detections")
async def post_detection(payload: DetectionPayload) -> Dict[str, Any]:
    return to_http(container.update_detection.execute(payload.node_id, payload.detected))


@router.post("/delete-flag")
async def delete_flag(payload: WebhookPayload) -> Dict[str, Any]:
    """Webhook ICS — gỡ system lock theo orderId (RAM + Mongo)."""
    return to_http(container.reset_flags.execute(payload.orderId, payload.status))


@router.get("/state/points")
async def get_all_points() -> Dict[str, Any]:
    result = container.get_all_points.execute()
    if not result.success:
        return to_http(result)
    return {"code": 1000, "message": "Success", "points": result.data["points"]}


@router.get("/state/zone/{zone}")
async def get_zone_state(zone: str) -> Dict[str, Any]:
    return to_http(await container.get_zone_state.execute(zone))
