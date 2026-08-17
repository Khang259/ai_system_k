"""Use case tests — runtime control + dispatch cycle."""
import asyncio

from application.runtime.control import (
    StartRuntime,
    StopRuntime,
    GetRuntimeStatus,
    ReloadRuntime,
)
from application.dispatch.run_cycle import RunDispatchCycle
from tests.application.fakes import (
    FakeDispatchGateway,
    FakeNodeStateStore,
    FakeRuntimeControl,
)


def test_runtime_start_stop_status_reload():
    rt = FakeRuntimeControl()
    started = asyncio.run(StartRuntime(rt).execute())
    assert started.success
    assert started.data["running"] is True
    assert rt.starts == 1

    status = GetRuntimeStatus(rt).execute()
    assert status.data["running"] is True

    stopped = StopRuntime(rt).execute()
    assert stopped.data["running"] is False
    assert rt.stops == 1

    reloaded = asyncio.run(ReloadRuntime(rt).execute())
    assert reloaded.data["running"] is True
    assert rt.reloads == 1


def test_run_dispatch_cycle_success_and_fail():
    validate = [("start_1", "end_1")]
    store = FakeNodeStateStore(validate_pairs=validate)
    store._ns.ready_start_list.add("start_1")
    store._ns.ready_end_list.add("end_1")

    gw = FakeDispatchGateway(ok=True)
    ok = RunDispatchCycle(store, gw).execute()
    assert ok.success
    assert len(ok.data["sent"]) == 1
    assert store._ns.points["start_1"]["flag"] is True
    assert len(gw.sent) == 1
    ics = gw.sent[0]
    assert ics["modelProcessCode"] == "SingleGroupAE5"
    assert ics["taskOrderDetail"][0]["taskPath"] == "1,1"
    assert ics["orderId"].startswith("S-1-1-")

    store2 = FakeNodeStateStore(validate_pairs=validate)
    store2._ns.ready_start_list.add("start_1")
    store2._ns.ready_end_list.add("end_1")
    gw2 = FakeDispatchGateway(ok=False)
    fail = RunDispatchCycle(store2, gw2).execute()
    assert fail.success
    assert fail.data["failed"]
    assert store2._ns.points["start_1"]["flag"] is False


def test_run_dispatch_cycle_not_ready():
    store = FakeNodeStateStore(ready=False)
    result = RunDispatchCycle(store, FakeDispatchGateway()).execute()
    assert not result.success
