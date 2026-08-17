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
    return to_http(container.reset_flags.execute(payload.orderId, payload.status))


@router.post("/state/flag/{node_id}")
async def toggle_flag(node_id: str) -> Dict[str, Any]:
    return to_http(container.toggle_flag.execute(node_id))


@router.get("/state/points")
async def get_all_points() -> Dict[str, Any]:
    result = container.get_all_points.execute()
    if not result.success:
        return to_http(result)
    return {"code": 1000, "message": "Success", "points": result.data["points"]}


@router.get("/state/zone/{zone}")
async def get_zone_state(zone: str) -> Dict[str, Any]:
    return to_http(container.get_zone_state.execute(zone))
