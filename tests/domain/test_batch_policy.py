"""Unit tests — batch scan policy."""

from domain.batch_policy import (
    find_new_nodes,
    idle_batch,
    record_dispatch_success,
    should_auto_pause,
    should_pause_for_new_nodes,
    start_batch,
)


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


def test_idle_batch():
    batch = idle_batch()
    assert batch.active is False
    assert batch.size == 0
