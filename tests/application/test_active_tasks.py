"""Panel order đang chạy — hub + use cases (fake ICS, fake reset)."""
import asyncio

from application.dispatch.active_task_hub import (
    TASK_EVENT,
    TASK_REMOVED_EVENT,
    ActiveTaskHub,
)
from application.dispatch.active_tasks import (
    GetActiveTasks,
    StartPriorityReader,
    TrackDispatchedTask,
    UnlockByOrderStatus,
)
from application.result import UseCaseResult

ORDER_A = "S-10000061-10000761-2026-10-03 09:51:33.123456"
ORDER_B = "S-10000071-10000770-2026-10-03 09:52:00.000001"
META = {
    "start_10000061": {"priority": 2},
    "start_10000071": {"priority": 1},
}


class _Nodes:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def get_all(self):
        return self.docs


class _Query:
    def __init__(self, tasks=None, error=None):
        self.tasks = tasks or []
        self.error = error

    def get_order_list(self, area_id):
        if self.error:
            raise self.error
        return self.tasks


class _Reset:
    def __init__(self, result=None):
        self.result = result or UseCaseResult.ok(message="ok", orderId="x")
        self.calls = []

    def execute(self, order_id, status):
        self.calls.append((order_id, status))
        return self.result


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def _priorities(meta=None, docs=None):
    return StartPriorityReader(_Nodes(docs), lambda: meta or {})


def test_track_dispatched_task_publishes_issued():
    hub = ActiveTaskHub()
    q = hub.subscribe()
    TrackDispatchedTask(hub, lambda: META).execute(ORDER_A)

    events = _drain(q)
    assert events[0][0] == TASK_EVENT
    assert events[0][1]["status"] == "issued"
    assert events[0][1]["priorityStart"] == 2


def test_get_active_tasks_filters_and_sorts():
    tasks = [
        {"OrderId": ORDER_A, "OrderStatus": 9},
        {"OrderId": ORDER_B, "OrderStatus": 6},
        {"OrderId": "S-10000080-10000780-2026-10-03 09:00:00", "OrderStatus": 3},
        {"OrderNumber": "RCS-44-1790995893186", "OrderStatus": 9},
    ]
    hub = ActiveTaskHub()
    uc = GetActiveTasks(_Query(tasks), hub, _priorities(META), area_id=1)

    result = asyncio.run(uc.execute())

    assert result.success
    items = result.data["items"]
    assert [it["orderId"] for it in items] == [ORDER_B, ORDER_A]
    assert [it["status"] for it in items] == ["inprogress", "issued"]
    assert hub.list_items() == items


def test_get_active_tasks_reads_mongo_when_runtime_not_started():
    docs = [{"node_id": "start_10000061", "node_type": "start", "priority": 5}]
    uc = GetActiveTasks(
        _Query([{"OrderId": ORDER_A, "OrderStatus": 9}]),
        ActiveTaskHub(),
        _priorities(meta=None, docs=docs),
        area_id=1,
    )
    result = asyncio.run(uc.execute())
    assert result.data["items"][0]["priorityStart"] == 5


def test_get_active_tasks_removes_stale_orders():
    hub = ActiveTaskHub()
    TrackDispatchedTask(hub, lambda: META).execute(ORDER_A)
    q = hub.subscribe()

    uc = GetActiveTasks(_Query([]), hub, _priorities(META), area_id=1)
    asyncio.run(uc.execute())

    assert hub.list_items() == []
    assert (TASK_REMOVED_EVENT, {"orderId": ORDER_A}) in _drain(q)


def test_get_active_tasks_ics_error_is_502():
    uc = GetActiveTasks(
        _Query(error=RuntimeError("timeout")), ActiveTaskHub(), _priorities(), area_id=1
    )
    result = asyncio.run(uc.execute())
    assert result.success is False
    assert result.data["http_status"] == 502


def test_webhook_6_updates_existing_order():
    hub = ActiveTaskHub()
    TrackDispatchedTask(hub, lambda: META).execute(ORDER_A)
    uc = UnlockByOrderStatus(_Reset(), hub, _priorities(META))

    result = asyncio.run(uc.execute(ORDER_A, 6))

    assert result.success
    assert hub.list_items()[0]["status"] == "inprogress"


def test_webhook_6_adds_unknown_order():
    hub = ActiveTaskHub()
    uc = UnlockByOrderStatus(_Reset(), hub, _priorities(META))

    asyncio.run(uc.execute(ORDER_B, 6))

    item = hub.list_items()[0]
    assert item["startNodeId"] == "start_10000071"
    assert item["priorityStart"] == 1


def test_webhook_23_resets_and_removes():
    hub = ActiveTaskHub()
    TrackDispatchedTask(hub, lambda: META).execute(ORDER_A)
    reset = _Reset()
    uc = UnlockByOrderStatus(reset, hub, _priorities(META))

    result = asyncio.run(uc.execute(ORDER_A, 23))

    assert result.success
    assert reset.calls == [(ORDER_A, 23)]
    assert hub.list_items() == []


def test_webhook_3_canceled_resets_and_removes_like_23():
    hub = ActiveTaskHub()
    TrackDispatchedTask(hub, lambda: META).execute(ORDER_A)
    reset = _Reset()
    uc = UnlockByOrderStatus(reset, hub, _priorities(META))

    result = asyncio.run(uc.execute(ORDER_A, 3))

    assert result.success
    assert reset.calls == [(ORDER_A, 3)]
    assert hub.list_items() == []


def test_webhook_other_status_ignored():
    hub = ActiveTaskHub()
    TrackDispatchedTask(hub, lambda: META).execute(ORDER_A)
    reset = _Reset()
    uc = UnlockByOrderStatus(reset, hub, _priorities(META))

    result = asyncio.run(uc.execute(ORDER_A, 8))

    assert result.success
    assert reset.calls == []
    assert hub.list_items()[0]["status"] == "issued"
