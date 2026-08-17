"""
Reset flags after AMR webhook (status 3 / 23).

Works on any object with NodeState-like attributes:
points, ready_start_list, ready_end_list, pair_mapping, order_mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

from domain.models import ResetStatus

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

    if status == ResetStatus.COMPLETED or status == int(ResetStatus.COMPLETED):
        return _reset_all(state, order_id, pairs)

    if status == ResetStatus.EMPTY_DONE or status == int(ResetStatus.EMPTY_DONE):
        return _reset_empty(state, order_id, pairs)

    return ResetResult(
        success=False,
        message="",
        order_id=order_id,
        error=f"Unknown status {status}",
    )


def _clear_pair(state: Any, start: str, end: str) -> None:
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


def _reset_empty(state: Any, order_id: str, pairs: Sequence[OrderPair]) -> ResetResult:
    remaining: List[OrderPair] = []
    reset_pairs: List[List[str]] = []

    for start, end, empty_car in pairs:
        if empty_car:
            _clear_pair(state, start, end)
            reset_pairs.append([start, end])
        else:
            remaining.append((start, end, empty_car))

    if remaining:
        state.order_mapping[order_id] = remaining
    else:
        del state.order_mapping[order_id]

    return ResetResult(
        success=True,
        message=f"Empty pairs reset for orderId {order_id}",
        order_id=order_id,
        reset_pairs=reset_pairs,
    )
