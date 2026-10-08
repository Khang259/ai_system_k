"""Unit tests — reset flags policy (task status 3 = Canceled, 23 = Placed)."""

from domain.models import OrderStatus
from domain.node_state import NodeState
from domain.reset_policy import reset_flags_by_order


def test_reset_all_status_placed():
    state = NodeState([])
    state.set_pair_used("start_1", "end_1", "ORD-1")

    result = reset_flags_by_order(state, "ORD-1", OrderStatus.PLACED)

    assert result.success is True
    assert result.reset_pairs == [["start_1", "end_1"]]
    assert "ORD-1" not in state.order_mapping
    assert state.points["start_1"]["flag"] is False
    assert state.points["end_1"]["flag"] is False
    assert "end_1" not in state.pair_mapping


def test_status_3_canceled_resets_like_placed():
    state = NodeState([])
    state.set_pair_used("start_1", "end_1", "ORD-2")

    result = reset_flags_by_order(state, "ORD-2", OrderStatus.CANCELED)

    assert result.success is True
    assert "ORD-2" not in state.order_mapping
    assert state.points["start_1"]["flag"] is False


def test_reset_unknown_order_and_status():
    state = NodeState([])
    missing = reset_flags_by_order(state, "NOPE", 23)
    assert missing.success is False

    state.set_pair_used("start_1", "end_1", "ORD-3")
    bad = reset_flags_by_order(state, "ORD-3", 99)
    assert bad.success is False
    assert "Unknown status" in bad.error
