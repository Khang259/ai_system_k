"""Smoke — SingleDispatch inject on_dispatch_success qua DispatchService."""
from application.dispatch.dispatch_service import DispatchService
from domain.node_state import NodeState
from infrastructure.adapters import NodeStateAdapter
from infrastructure.dispatch.pair_manager import PairManager, SingleDispatch


class _FakeGateway:
    def __init__(self, ok=True):
        self.ok = ok
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)
        return self.ok


class _FakeState:
    def __init__(self):
        self.used = []

    def set_pair_used(self, start, end, order_id, empty_car=False):
        self.used.append((start, end, order_id, empty_car))


def test_single_dispatch_calls_on_dispatch_success():
    gw = _FakeGateway(ok=True)
    state = _FakeState()
    called = []

    SingleDispatch(DispatchService(gw)).execute(
        pairs=[("start_1", "end_1")],
        pending_empty_queue=[],
        state_manager=state,
        on_dispatch_success=lambda nid: called.append(nid),
    )

    assert called == ["start_1"]
    assert len(gw.sent) == 1
    assert state.used and state.used[0][0] == "start_1"


def test_single_dispatch_skips_callback_on_fail():
    gw = _FakeGateway(ok=False)
    called = []

    SingleDispatch(DispatchService(gw)).execute(
        pairs=[("start_1", "end_1")],
        pending_empty_queue=[],
        state_manager=_FakeState(),
        on_dispatch_success=lambda nid: called.append(nid),
    )

    assert called == []


def test_make_pairs_with_adapter_covers_runtime_path():
    """
    Regression: runtime_service phải bọc NodeState bằng NodeStateAdapter.
    NodeState thô làm make_pairs vỡ — domain chỉ có attribute ready_start_list,
    còn PairManager/DispatchService gọi method ready_starts() của port.

    Test đi qua đúng đường runtime: make_pairs → ready_starts + build_pairs.
    """
    ns = NodeState([("start_1", "end_1"), ("start_empty",)])
    ns.ready_start_list.update({"start_1", "start_empty"})
    ns.ready_end_list.add("end_1")

    gw = _FakeGateway()
    pm = PairManager(
        state_manager=NodeStateAdapter(ns),
        validate_pairs=[("start_1", "end_1"), ("start_empty",)],
        strategy=SingleDispatch(DispatchService(gw)),
        dispatch_service=DispatchService(gw),
    )
    pairs, empty = pm.make_pairs()

    assert pairs == [("start_1", "end_1")]
    assert empty == [("start_empty",)]


def test_adapter_process_ends_forwards_warn():
    """PairManager gọi process_ends(warn=...) — adapter phải nhận và chuyển tiếp."""
    NodeStateAdapter(NodeState([])).process_ends(warn=lambda *_: None)
