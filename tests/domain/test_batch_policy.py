"""Unit tests — batch scan policy + strict order theo zone."""

from domain.batch_policy import (
    allowed_pairs,
    find_new_nodes,
    idle_batch,
    record_dispatch_success,
    should_auto_pause,
    should_pause_for_new_nodes,
    start_batch,
    stuck_nodes,
    waiting_for,
    zone_heads,
)


META = {
    "start_1": {"priority": 1, "zone_id": "SBA"},
    "start_2": {"priority": 2, "zone_id": "SBA"},
    "start_11": {"priority": 1, "zone_id": "SBB"},
}


def test_start_batch_snapshots_nodes():
    batch = start_batch(["start_1", "start_2"])
    assert batch.active is True
    assert batch.size == 2
    assert batch.sum_request == 0


def test_auto_pause_when_dispatches_complete():
    batch = start_batch(["start_1", "start_2"])
    batch = record_dispatch_success(batch)
    assert should_auto_pause(batch) is False

    batch = record_dispatch_success(batch)
    assert should_auto_pause(batch) is True
    assert batch.remaining == 0


def test_find_new_nodes_and_pause_guard():
    snapshot = {"start_1"}
    current = {"start_1", "start_99"}
    assert find_new_nodes(current, snapshot) == {"start_99"}
    assert should_pause_for_new_nodes(current, snapshot) == {"start_99"}
    assert should_pause_for_new_nodes(snapshot, snapshot) is None


def test_zone_heads_are_lowest_priority_per_zone():
    batch = start_batch(["start_1", "start_2", "start_11"])
    assert zone_heads(batch, META) == {"SBA": "start_1", "SBB": "start_11"}

    batch = record_dispatch_success(batch, "start_1")
    assert zone_heads(batch, META) == {"SBA": "start_2", "SBB": "start_11"}


def test_strict_order_blocks_non_head_in_same_zone():
    """start_1 bị che → không nhảy sang start_2 cùng zone."""
    pairs = [
        ("start_2", "end_a"),
        ("start_11", "end_b"),
        ("start_1", "end_a"),
    ]
    batch = start_batch(["start_1", "start_2", "start_11"])
    # start_1 không ready → chỉ còn cặp của heads đang ready trong pairs
    assert allowed_pairs(batch, pairs[:2], META) == [("start_11", "end_b")]


def test_busy_zone_blocks_next_head():
    """Zone đang có lệnh (lock) → không gửi head kế dù ready."""
    pairs = [("start_2", "end_a"), ("start_11", "end_b")]
    batch = start_batch(["start_1", "start_2", "start_11"])
    batch = record_dispatch_success(batch, "start_1")
    assert allowed_pairs(batch, pairs, META, locked_starts=["start_1"]) == [
        ("start_11", "end_b")
    ]
    assert allowed_pairs(batch, pairs, META, locked_starts=[]) == pairs


def test_waiting_for_and_stuck_nodes():
    batch = start_batch(["start_1", "start_2", "start_11"])
    assert waiting_for(batch, META, ready_starts={"start_2", "start_11"}) == [
        {"zoneId": "SBA", "nodeId": "start_1"}
    ]
    assert stuck_nodes(batch, {"start_2", "start_11"}) == ["start_1"]
    assert waiting_for(idle_batch(), META, {"start_1"}) == []


def test_idle_batch():
    batch = idle_batch()
    assert batch.active is False
    assert batch.size == 0
