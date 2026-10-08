"""DispatchGate + GetPendingPairs — strict order theo zone + cancel-batch."""
from application.cameras.cancel_batch import CancelBatch
from application.dispatch.dispatch_gate import DispatchGate
from application.dispatch.pending_pairs import GetPendingPairs
from application.scan_session import ScanSession
from domain.batch_policy import dispatchable_starts
from tests.application.fakes import FakeInference, FakeNodeStateStore

META = {
    "start_1": {"priority": 1, "zone_id": "SBA"},
    "start_2": {"priority": 2, "zone_id": "SBA"},
    "start_3": {"priority": 3, "zone_id": "SBA"},
    "start_11": {"priority": 1, "zone_id": "SBB"},
}

PAIRS = [
    ("start_1", "end_a"),
    ("start_2", "end_a"),
    ("start_3", "end_a"),
    ("start_11", "end_b"),
]


def _gate(scan=None):
    return DispatchGate(scan or ScanSession(), lambda: META)


def test_gate_closed_blocks_all_pairs():
    assert _gate().filter(PAIRS, {"start_1"}) == []


def test_strict_order_same_zone_only_head():
    scan = ScanSession()
    scan.start(["start_1", "start_2", "start_11"])
    gate = _gate(scan)

    # start_1 chưa ready → SBA chờ; SBB gửi start_11
    assert gate.filter(
        [("start_2", "end_a"), ("start_11", "end_b")],
        {"start_2", "start_11"},
    ) == [("start_11", "end_b")]

    # start_1 ready → gửi start_1, không gửi start_2
    assert gate.filter(
        [("start_1", "end_a"), ("start_2", "end_a"), ("start_11", "end_b")],
        {"start_1", "start_2", "start_11"},
    ) == [("start_1", "end_a"), ("start_11", "end_b")]


def test_busy_zone_waits_for_lock_clear():
    scan = ScanSession()
    scan.start(["start_1", "start_2"])
    scan.record_success("start_1")
    gate = _gate(scan)

    assert gate.filter(
        [("start_2", "end_a")],
        {"start_2"},
        locked_starts=["start_1"],
    ) == []
    assert gate.filter([("start_2", "end_a")], {"start_2"}) == [("start_2", "end_a")]


def test_gate_halts_when_ready_start_outside_batch():
    scan = ScanSession()
    scan.start(["start_1", "start_2"])
    gate = _gate(scan)

    assert gate.filter(PAIRS, {"start_1", "start_3"}) == []
    status = scan.status()
    assert not status["active"]
    assert status["stopReason"] == "new_nodes"
    assert status["newNodes"] == ["start_3"]


def test_cancel_batch_closes_gate_keeps_inference():
    scan = ScanSession()
    scan.start(["start_1", "start_2"])
    inf = FakeInference(paused=False)

    ok = CancelBatch(scan).execute()
    assert ok.success
    assert ok.data["remaining"] == ["start_1", "start_2"]
    assert not scan.get().active
    assert scan.status()["stopReason"] == "canceled"
    assert inf.pause_calls == 0

    again = CancelBatch(scan).execute()
    assert again.data["http_status"] == 409


def test_pending_pairs_waiting_for_and_stuck():
    pairs = [["start_1", "end_a"], ["start_2", "end_a"], ["start_11", "end_b"]]
    state = FakeNodeStateStore(validate_pairs=pairs)
    state._ns.ready_start_list.update({"start_2", "start_11"})
    state._ns.ready_end_list.update({"end_a", "end_b"})
    scan = ScanSession()
    scan.start(["start_1", "start_2", "start_11"])
    uc = GetPendingPairs(state, scan, lambda: META)

    data = uc.execute().data
    assert data["waitingFor"] == [{"zoneId": "SBA", "nodeId": "start_1"}]
    assert data["stuckNodes"] == ["start_1"]
    assert data["nextPairs"] == [{"startNodeId": "start_11", "endNodeId": "end_b"}]


def test_dispatchable_starts_drops_start_empty():
    pairs = [("start_1", "end_1"), ("start_empty",)]
    assert dispatchable_starts({"start_1", "start_empty"}, pairs) == {"start_1"}


def test_pending_pairs_runtime_not_ready():
    data = GetPendingPairs(FakeNodeStateStore(ready=False), ScanSession(), dict).execute().data
    assert data["runtimeReady"] is False
    assert data["nextPairs"] == []
    assert data["waitingFor"] == []
