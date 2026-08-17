"""Smoke — SingleDispatch inject on_dispatch_success, không import service shim."""
from infrastructure.dispatch.pair_manager import SingleDispatch


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

    SingleDispatch(gw).execute(
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

    SingleDispatch(gw).execute(
        pairs=[("start_1", "end_1")],
        pending_empty_queue=[],
        state_manager=_FakeState(),
        on_dispatch_success=lambda nid: called.append(nid),
    )

    assert called == []
