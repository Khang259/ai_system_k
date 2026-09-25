"""Use case tests — state (fake NodeStateStore, no RTSP/model)."""
from domain.models import ResetStatus
from application.state.reset_flags import ResetFlagsByOrder
from tests.application.fakes import FakeNodeStateStore


def test_user_lock_blocks_ready_semantics():
    store = FakeNodeStateStore()
    store.update_detection("start_1", True)
    store.apply_persisted_lock("start_1", user=True)
    assert store.lock_view("start_1")["user"] is True
    assert store._ns.points["start_1"]["flag"] is True

    store.apply_persisted_lock("start_1", user=False)
    assert store.lock_view("start_1")["user"] is False


def test_reset_flags_completed_and_empty():
    store = FakeNodeStateStore()
    store.set_pair_used("start_1", "end_1", "ORD-1", empty_car=False)
    store.set_pair_used("start_e", "end_e", "ORD-1", empty_car=True)
    uc = ResetFlagsByOrder(store)

    empty = uc.execute("ORD-1", int(ResetStatus.EMPTY_DONE))
    assert empty.success
    assert empty.data["reset_pairs"] == [["start_e", "end_e"]]
    assert store._ns.points["start_1"]["flag"] is True

    all_reset = uc.execute("ORD-1", int(ResetStatus.COMPLETED))
    assert all_reset.success
    assert "reset_pairs" not in all_reset.data
    assert "ORD-1" not in store._ns.order_mapping
