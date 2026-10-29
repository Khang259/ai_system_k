"""Unit tests — batch scan policy + col order (zone lock)."""

from domain.batch_policy import (
    allowed_pairs,
    find_new_nodes,
    idle_batch,
    plan_col_dispatch,
    record_dispatch_success,
    should_auto_pause,
    start_batch,
    stuck_nodes,
)


META = {
    "start_1": {"priority": 1, "zone_id": "SBA", "col_id": "A"},
    "start_2": {"priority": 2, "zone_id": "SBA", "col_id": "A"},
    "start_11": {"priority": 1, "zone_id": "SBB", "col_id": "A"},
}


def test_start_batch_snapshots_nodes():
    batch = start_batch(["start_1", "start_2"])
    assert batch.active is True
    assert batch.size == 2
    assert batch.sum_request == 0


def test_auto_pause_when_dispatches_complete():
    batch = start_batch(["start_1", "start_2"])
    batch = record_dispatch_success(batch, "start_1")
    assert should_auto_pause(batch) is False

    batch = record_dispatch_success(batch, "start_2")
    assert should_auto_pause(batch) is True
    assert batch.remaining == 0


def test_find_new_nodes_no_longer_halts():
    """Node mới ngoài batch chỉ báo cáo — không pause guard."""
    snapshot = {"start_1"}
    current = {"start_1", "start_99"}
    assert find_new_nodes(current, snapshot) == {"start_99"}


def test_col_heads_lowest_priority_per_col_zone():
    batch = start_batch(["start_1", "start_2", "start_11"])
    plan = plan_col_dispatch(batch, META)
    # Hai zone → hai allow song song
    assert plan.allow_starts == frozenset({"start_1", "start_11"})

    batch = record_dispatch_success(batch, "start_1")
    plan = plan_col_dispatch(batch, META)
    assert "start_2" in plan.allow_starts
    assert "start_11" in plan.allow_starts


def test_strict_order_blocks_non_head_in_same_col():
    pairs = [
        ("start_2", "end_a"),
        ("start_11", "end_b"),
        ("start_1", "end_a"),
    ]
    batch = start_batch(["start_1", "start_2", "start_11"])
    assert allowed_pairs(batch, pairs[:2], META) == [("start_11", "end_b")]


def test_busy_zone_blocks_next_head():
    pairs = [("start_2", "end_a"), ("start_11", "end_b")]
    batch = start_batch(["start_1", "start_2", "start_11"])
    batch = record_dispatch_success(batch, "start_1")
    assert allowed_pairs(batch, pairs, META, locked_starts=["start_1"]) == [
        ("start_11", "end_b")
    ]
    assert set(allowed_pairs(batch, pairs, META, locked_starts=[])) == set(pairs)


def test_stuck_nodes_informational():
    batch = start_batch(["start_1", "start_2", "start_11"])
    assert stuck_nodes(batch, {"start_2", "start_11"}) == ["start_1"]


def test_filled_excluded_from_stuck():
    from domain.batch_policy import filled_nodes

    batch = start_batch(
        ["start_1", "start_2", "start_11"],
        filled=["start_1"],
    )
    assert filled_nodes(batch) == ["start_1"]
    assert stuck_nodes(batch, {"start_2", "start_11"}) == []


def test_idle_batch():
    batch = idle_batch()
    assert batch.active is False
    assert batch.size == 0
    assert batch.filled == frozenset()
