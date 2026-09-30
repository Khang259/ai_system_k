"""Runtime node snapshot + SSE hub."""
from __future__ import annotations

import asyncio
import time

from application.fe_api.poll import GetPollSnapshot
from application.fe_api.runtime_nodes import GetNodeRuntimeState
from application.null_ports import NullMapStateStore, NullNotificationStore
from application.result import UseCaseResult
from application.runtime.runtime_state_hub import RuntimeStateHub, map_runtime_item
from domain.node_state import NodeState
from tests.application.fakes import FakeNodeStateStore


def _run(coro):
    return asyncio.run(coro)


class _Cam:
    async def execute(self):
        return UseCaseResult.ok(items=[])


class _Zones:
    async def execute(self):
        return UseCaseResult.ok(items=[])


def test_map_runtime_item_shape():
    item = map_runtime_item(
        "start_1",
        {
            "detected": True,
            "isReady": True,
            "lock": {"user": False, "system": True, "orderId": "O1"},
        },
    )
    assert item == {
        "nodeId": "start_1",
        "detected": True,
        "isReady": True,
        "lock": {"user": False, "system": True, "orderId": "O1"},
    }


def test_get_runtime_state_not_ready():
    store = FakeNodeStateStore(ready=False)
    r = GetNodeRuntimeState(store).execute()
    assert r.success
    assert r.data["runtimeReady"] is False
    assert r.data["items"] == []


def test_get_runtime_state_ready_with_fields():
    store = FakeNodeStateStore()
    store.update_detection("start_1", True)
    store.apply_persisted_lock("start_1", system=True, order_id="ORD-9")
    store._ns.ready_start_list.add("start_1")

    r = GetNodeRuntimeState(store).execute()
    assert r.success
    assert r.data["runtimeReady"] is True
    item = r.data["items"][0]
    assert item["nodeId"] == "start_1"
    assert item["detected"] is True
    assert item["isReady"] is True
    assert item["lock"]["system"] is True
    assert item["lock"]["orderId"] == "ORD-9"


def test_poll_include_nodes():
    store = FakeNodeStateStore()
    store.update_detection("start_1", True)
    rt = GetNodeRuntimeState(store)
    uc = GetPollSnapshot(
        _Cam(),
        _Zones(),
        NullNotificationStore(),
        NullMapStateStore(),
        get_runtime_nodes=rt,
    )
    r = _run(uc.execute("u-1", include={"nodes"}))
    assert "nodes" in r.data
    assert r.data["nodes"]["runtimeReady"] is True
    assert r.data["nodes"]["items"][0]["nodeId"] == "start_1"
    assert "cameras" not in r.data


def test_hub_debounce_emits_mapped_item():
    ns = NodeState([])
    hub = RuntimeStateHub(debounce_ms=50)
    hub.bind_snapshot(lambda: ns.snapshot_points())
    ns.set_change_listener(hub.touch)
    q = hub.subscribe()

    ns.get_state_nodes("start_1", True)
    ns.get_state_nodes("start_1", False)
    ns.get_state_nodes("start_1", True)

    deadline = time.time() + 1.0
    item = None
    while time.time() < deadline:
        try:
            item = q.get(timeout=0.1)
            break
        except Exception:
            continue
    assert item is not None
    assert item["nodeId"] == "start_1"
    assert item["detected"] is True
    hub.unsubscribe(q)
