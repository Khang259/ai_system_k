"""Unit tests — col dispatch: accessible head (stack-based), remaining/skipped."""

from domain.batch_policy import (
    plan_col_dispatch,
    record_dispatch_success,
    record_skip,
    should_auto_pause,
    start_batch,
)

META = {
    "start_1": {"priority": 1, "zone_id": "Z1", "col_id": "A"},
    "start_2": {"priority": 2, "zone_id": "Z1", "col_id": "A"},
    "start_3": {"priority": 3, "zone_id": "Z1", "col_id": "A"},
    "start_4": {"priority": 4, "zone_id": "Z1", "col_id": "B"},
    "start_5": {"priority": 5, "zone_id": "Z1", "col_id": "B"},
    "start_6": {"priority": 6, "zone_id": "Z1", "col_id": "B"},
    "start_7": {"priority": 7, "zone_id": "Z1", "col_id": "C"},
    "start_8": {"priority": 8, "zone_id": "Z1", "col_id": "C"},
    "start_9": {"priority": 9, "zone_id": "Z1", "col_id": "C"},
}


def test_plan_allows_col_a_head_first():
    batch = start_batch([f"start_{i}" for i in range(1, 10)])
    plan = plan_col_dispatch(batch, META)
    assert plan.allow_starts == frozenset({"start_1"})
    assert plan.skip_nodes == frozenset()


def test_empty_slot_before_allows_next_accessible():
    """
    Stack logic: node 5 trống (không trong batch) = lối đi thông.
    Batch thiếu 5 → sau khi gửi 1-4, head col B = 6 (vì 4,5 đều trống).
    """
    batch = start_batch(
        ["start_1", "start_2", "start_3", "start_4", "start_6", "start_7", "start_8", "start_9"]
    )
    for nid in ("start_1", "start_2", "start_3", "start_4"):
        batch = record_dispatch_success(batch, nid)

    plan = plan_col_dispatch(batch, META)
    # Node 5 trống → node 6 accessible → allow col B head = 6
    assert plan.allow_starts == frozenset({"start_6"})
    assert plan.skip_nodes == frozenset()  # Không còn skip logic


def test_manual_skip_then_allow_col_c():
    """Manual skip vẫn hoạt động — dùng khi cần skip thủ công."""
    batch = start_batch(
        ["start_1", "start_2", "start_3", "start_4", "start_6", "start_7", "start_8", "start_9"]
    )
    for nid in ("start_1", "start_2", "start_3", "start_4"):
        batch = record_dispatch_success(batch, nid)
    batch = record_skip(batch, ["start_6"])
    plan = plan_col_dispatch(batch, META)
    # Col B skipped thủ công → head col C = 7
    assert plan.allow_starts == frozenset({"start_7"})
    assert plan.skip_nodes == frozenset()


def test_tc04_only_mid_nodes_ready_allows_accessible():
    """
    Stack logic: Batch {2,5,8} với nodes 1,4,7 trống (không có hàng).
    - Col A: 1 trống → head = 2 accessible ✓
    - Chỉ 1 lệnh/zone → allow 2
    """
    batch = start_batch(["start_2", "start_5", "start_8"])
    plan = plan_col_dispatch(batch, META)
    # Node 1 trống → node 2 accessible → head col A = 2
    assert plan.allow_starts == frozenset({"start_2"})
    assert plan.skip_nodes == frozenset()  # Không còn skip logic


def test_remaining_with_skipped():
    batch = start_batch(["start_1", "start_2", "start_3"])
    batch = record_dispatch_success(batch, "start_1")
    batch = record_skip(batch, ["start_2", "start_3"])
    assert batch.remaining == 0
    assert should_auto_pause(batch) is True


def test_busy_zone_waits_no_allow():
    """Zone bị lock → chờ, không allow."""
    batch = start_batch([f"start_{i}" for i in range(1, 10)])
    batch = record_dispatch_success(batch, "start_1")
    plan = plan_col_dispatch(batch, META, locked_starts=["start_1"])
    assert plan.allow_starts == frozenset()
    assert any(w.get("reason") == "zone_locked" for w in plan.waiting)


def test_blocked_by_pending_node_in_front():
    """
    Batch {1, 3}: node 2 trống, nhưng node 1 chặn đường đến node 3.
    - Node 1 ∈ pending → head = 1
    - Node 3 bị chặn bởi node 1 (dù node 2 trống)
    """
    batch = start_batch(["start_1", "start_3"])
    plan = plan_col_dispatch(batch, META)
    # Head = 1 (node đầu tiên accessible), node 3 chờ sau
    assert plan.allow_starts == frozenset({"start_1"})


def test_sequential_dispatch_with_empty_middle():
    """
    Batch {1, 3} với node 2 trống: dispatch 1 xong → head = 3.
    Layout: [1] - [2] - [3] (entrance → deep)
    - Dispatch 1 → 1 trống
    - Node 2 trống từ đầu
    - Node 3: nodes_before = [1,2], cả hai trống → head = 3 ✓
    """
    batch = start_batch(["start_1", "start_3"])
    batch = record_dispatch_success(batch, "start_1")
    plan = plan_col_dispatch(batch, META)
    assert plan.allow_starts == frozenset({"start_3"})


def test_all_front_nodes_empty_allows_deep_node():
    """
    Batch {3} với nodes 1,2 trống: head = 3 ngay lập tức.
    Layout: [1✗] - [2✗] - [3✓]
    """
    batch = start_batch(["start_3"])
    plan = plan_col_dispatch(batch, META)
    assert plan.allow_starts == frozenset({"start_3"})


def test_multi_col_with_partial_fill():
    """
    Scenario thực tế: Col A fill 2,3 (node 1 trống), Col B fill 5,6 (node 4 trống).
    Batch = {2, 3, 5, 6}
    - Col A: 1 trống → head = 2 ✓
    - Col B: 4 trống → head = 5 (nhưng chỉ 1 lệnh/zone)
    """
    batch = start_batch(["start_2", "start_3", "start_5", "start_6"])
    plan = plan_col_dispatch(batch, META)
    # Col A: head = 2 (1 trống), 1 lệnh/zone
    assert plan.allow_starts == frozenset({"start_2"})
    assert "Z1|A" in plan.col_heads
    assert plan.col_heads["Z1|A"] == "start_2"
