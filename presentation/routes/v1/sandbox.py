"""Sandbox routes — `/api/v1/sandbox/*`. Chỉ mount khi RUNTIME_MODE=sandbox."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request

from application.container import container
from application.runtime.runtime_service import runtime_service
from domain.dispatch.active_task import parse_order_id
from domain.permissions import SYSTEM_CONTROL
from infrastructure.sandbox.smoke_trail import emit, inference_paused, node_runtime_view
from presentation.deps import require_permission
from presentation.http_v1 import system_audited_or_error
from presentation.schemas import OrderStatusWebhookPayload, SandboxNodeStatePayload

router = APIRouter()


def _sandbox() -> Tuple[Any, Any]:
    cameras = runtime_service.component("camera_manager")
    ics = runtime_service.component("ics_gateway")
    if not hasattr(cameras, "set_node_state") or not hasattr(ics, "get_orders"):
        raise HTTPException(status_code=503, detail="Sandbox runtime chưa chạy")
    return cameras, ics


@router.get("/get_nodes", summary="State mong muốn của từng ROI node")
def get_nodes(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    cameras, _ = _sandbox()
    return {"items": cameras.get_node_states()}


@router.post("/set_node_state", summary="Đặt detected cho một node (phải thuộc ROI camera)")
def set_node_state(
    payload: SandboxNodeStatePayload,
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    cameras, _ = _sandbox()
    if not cameras.set_node_state(payload.nodeId, payload.detected):
        raise HTTPException(
            status_code=404, detail=f"Node {payload.nodeId} không thuộc ROI camera nào"
        )
    paused = inference_paused(runtime_service.component("inference_engine"))
    kind = (
        "start"
        if payload.nodeId.startswith("start_")
        else "end"
        if payload.nodeId.startswith("end_")
        else "unknown"
    )
    hint = None
    if paused:
        hint = (
            "Inference đang pause — desired đã lưu nhưng chưa đẩy vào NodeState "
            "cho đến khi start-scan"
        )
    elif kind == "start" and not payload.detected:
        hint = "Tắt hàng start — làm trước khi báo status 3 để tránh start ready lại"
    elif kind == "end" and payload.detected:
        hint = "End detected=true = có hàng (bận); smoke thường để end trống (false)"

    emit(
        "api",
        "set_node_state",
        nodeId=payload.nodeId,
        kind=kind,
        detected=payload.detected,
        inferencePaused=paused,
        nodes=node_runtime_view(container.state, payload.nodeId),
        hint=hint,
    )
    return {"nodeId": payload.nodeId, "detected": payload.detected}


@router.get("/get_orders", summary="Lệnh ICS giả đã nhận, theo thứ tự gửi (seq)")
def get_orders(
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    _, ics = _sandbox()
    return {"items": ics.get_orders()}


@router.post(
    "/set_order_status",
    summary="ICS giả báo status (6 → inprogress, 3|23 → gỡ lock) — cùng luồng webhook thật",
)
async def set_order_status(
    payload: OrderStatusWebhookPayload,
    request: Request,
    _user: Dict[str, Any] = Depends(require_permission(SYSTEM_CONTROL)),
) -> Dict[str, Any]:
    _, ics = _sandbox()
    if not ics.set_status(payload.orderId, payload.status):
        raise HTTPException(status_code=404, detail=f"orderId {payload.orderId} không tồn tại")

    parsed = parse_order_id(payload.orderId)
    start_id = parsed[0] if parsed else None
    end_id = parsed[1] if parsed else None
    hint = None
    if payload.status in (3, 23):
        hint = (
            "Clear lock start+end — đảm bảo đã tắt detected start trước đó; "
            "end trống sẽ ready lại sau END_READY_AFTER_SEC"
        )
    elif payload.status == 6:
        hint = "Panel → inprogress"

    emit(
        "api",
        "set_order_status",
        orderId=payload.orderId,
        status=payload.status,
        startNodeId=start_id,
        endNodeId=end_id,
        nodes=node_runtime_view(container.state, start_id or "", end_id or ""),
        inferencePaused=inference_paused(runtime_service.component("inference_engine")),
        hint=hint,
    )

    result = await container.unlock_by_order_status_v1.execute(payload.orderId, payload.status)
    return await system_audited_or_error(
        result,
        request,
        "unlock_by_order_status",
        payload.model_dump(),
        order_id=payload.orderId,
    )
