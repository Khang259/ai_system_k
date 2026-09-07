"""Test DispatchService logic (không cần thread)."""
from application.dispatch.dispatch_service import DispatchService
from tests.application.fakes import FakeDispatchGateway, FakeNodeStateStore


def test_dispatch_service_single_success():
    gw = FakeDispatchGateway()
    gw.success = True
    store = FakeNodeStateStore()
    store.update_detection("start_1", True)
    store.update_detection("end_1", False)
    
    service = DispatchService(gw)
    sent, failed = service.dispatch_single(
        [("start_1", "end_1")],
        store,
    )
    
    assert len(sent) == 1
    assert sent[0]["start"] == "start_1"
    assert len(failed) == 0
    assert gw.sent_count == 1


def test_dispatch_service_single_fail():
    gw = FakeDispatchGateway()
    gw.success = False
    gw.ok = False  # Need to set ok too
    store = FakeNodeStateStore()
    
    service = DispatchService(gw)
    sent, failed = service.dispatch_single(
        [("start_2", "end_2")],
        store,
    )
    
    assert len(sent) == 0
    assert len(failed) == 1
    assert failed[0]["start"] == "start_2"


def test_dispatch_service_build_pairs():
    store = FakeNodeStateStore()
    store._ns.ready_start_list = ["start_1", "start_2"]
    store._ns.ready_end_list = ["end_1"]
    store._ns.validate_pairs = [("start_1", "end_1"), ("start_2", "end_2")]
    
    service = DispatchService(FakeDispatchGateway())
    pairs = service.build_pairs(store)
    
    assert len(pairs) == 1
    assert pairs[0] == ("start_1", "end_1")


def test_dispatch_service_empty():
    gw = FakeDispatchGateway()
    gw.success = True
    store = FakeNodeStateStore()
    
    queue = [("start_empty", 100.0)]
    
    service = DispatchService(gw)
    sent, failed = service.dispatch_empty(
        queue,
        "end_10001546",
        200.0,  # now > deadline
        store,
    )
    
    assert len(sent) == 1
    assert len(queue) == 0
    assert gw.sent_count == 1
