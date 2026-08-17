"""Unit tests — reset flags policy (status 3 / 23)."""

from domain.models import ResetStatus
from domain.node_state import NodeState
from domain.reset_policy import reset_flags_by_order


def _seed_order(state: NodeState, order_id: str, pairs):
    for start, end, empty in pairs:
        state.set_pair_used(start, end, order_id, empty_car=empty)


def test_reset_all_status_completed():
    state = NodeState([])
    _seed_order(
        state,
        "ORD-1",
        [("start_1", "end_1", False), ("start_e", "end_e", True)],
    )

    result = reset_flags_by_order(state, "ORD-1", ResetStatus.COMPLETED)

    assert result.success is True
    assert "ORD-1" not in state.order_mapping
    assert state.points["start_1"]["flag"] is False
    assert state.points["end_1"]["flag"] is False
    assert state.points["start_e"]["flag"] is False
    assert "end_1" not in state.pair_mapping


def test_reset_empty_only_keeps_normal_pair():
    state = NodeState([])
    _seed_order(
        state,
        "ORD-2",
        [("start_1", "end_1", False), ("start_e", "end_e", True)],
    )

    result = reset_flags_by_order(state, "ORD-2", ResetStatus.EMPTY_DONE)

    assert result.success is True
    assert result.reset_pairs == [["start_e", "end_e"]]
    assert state.order_mapping["ORD-2"] == [("start_1", "end_1", False)]
    assert state.points["start_1"]["flag"] is True
    assert state.points["start_e"]["flag"] is False


def test_reset_unknown_order_and_status():
    state = NodeState([])
    missing = reset_flags_by_order(state, "NOPE", 3)
    assert missing.success is False

    state.set_pair_used("start_1", "end_1", "ORD-3")
    bad = reset_flags_by_order(state, "ORD-3", 99)
    assert bad.success is False
    assert "Unknown status" in bad.error
