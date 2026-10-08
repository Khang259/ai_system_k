"""
Reset flags after ICS webhook (task status 3 = Canceled, 23 = Placed).

Works on any object with NodeState-like attributes:
points, ready_start_list, ready_end_list, pair_mapping, order_mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

from domain.models import OrderStatus

OrderPair = Tuple[str, str, bool]


@dataclass
class ResetResult:
    success: bool
    message: str
    order_id: str
    reset_pairs: List[List[str]] = field(default_factory=list)
    error: Optional[str] = None


def reset_flags_by_order(state: Any, order_id: str, status: int) -> ResetResult:
    pairs = state.order_mapping.get(order_id)
    if not pairs:
        return ResetResult(
            success=False,
            message="",
            order_id=order_id,
            error=f"orderId {order_id} not found",
        )

    if OrderStatus.clears_order(status):
        return _reset_all(state, order_id, pairs)

    return ResetResult(
        success=False,
        message="",
        order_id=order_id,
        error=f"Unknown status {status}",
    )


def _clear_pair(state: Any, start: str, end: str) -> None:
    if hasattr(state, "clear_system_lock"):
        state.clear_system_lock(start, end)
    else:
        state.points[start]["flag"] = False
        state.points[end]["flag"] = False
    state.ready_start_list.discard(start)
    state.ready_end_list.discard(end)
    state.pair_mapping.pop(end, None)


def _reset_all(state: Any, order_id: str, pairs: Sequence[OrderPair]) -> ResetResult:
    reset_pairs: List[List[str]] = []
    for start, end, _ in pairs:
        _clear_pair(state, start, end)
        reset_pairs.append([start, end])

    del state.order_mapping[order_id]
    return ResetResult(
        success=True,
        message=f"Flags reset for orderId {order_id}",
        order_id=order_id,
        reset_pairs=reset_pairs,
    )
