"""Active task (order đang chạy) — parse orderId + map status cho FE. Pure Python."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from domain.dispatch.priority import StartMetaMap, resolve_priority
from domain.models import OrderStatus

STATUS_LABELS = {
    OrderStatus.ASSIGNED: "issued",
    OrderStatus.RUNNING: "inprogress",
}


def parse_order_id(order_id: Any) -> Optional[Tuple[str, str]]:
    """`S-{start}-{end}-{time}` → (start_xxx, end_xxx). Sai format → None."""
    parts = str(order_id or "").split("-", 3)
    if len(parts) != 4 or parts[0] != "S":
        return None
    start_num, end_num = parts[1], parts[2]
    if not start_num.isdigit() or not end_num.isdigit():
        return None
    return f"start_{start_num}", f"end_{end_num}"


def status_label(code: Any) -> Optional[str]:
    """Task status ICS → label FE. Status không hiển thị → None."""
    try:
        return STATUS_LABELS.get(OrderStatus(int(code)))
    except (TypeError, ValueError):
        return None


def build_active_task(
    order_id: Any,
    status: str,
    start_meta: Optional[StartMetaMap] = None,
) -> Optional[Dict[str, Any]]:
    nodes = parse_order_id(order_id)
    if nodes is None:
        return None
    start, end = nodes
    meta = (start_meta or {}).get(start) or {}
    return {
        "orderId": str(order_id),
        "startNodeId": start,
        "endNodeId": end,
        "priorityStart": meta.get("priority"),
        "status": status,
    }


def sort_active_tasks(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """priorityStart ASC (thiếu → cuối), rồi orderId."""
    return sorted(
        items,
        key=lambda it: (resolve_priority(it.get("priorityStart")), it["orderId"]),
    )
