"""Use case tests — state (fake NodeStateStore, no RTSP/model)."""
from domain.models import OrderStatus
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


def test_reset_flags_placed():
    store = FakeNodeStateStore()
    store.set_pair_used("start_1", "end_1", "ORD-1", empty_car=False)
    uc = ResetFlagsByOrder(store)

    result = uc.execute("ORD-1", int(OrderStatus.PLACED))
    assert result.success
    assert "ORD-1" not in store._ns.order_mapping
    assert store._ns.points["start_1"]["flag"] is False
