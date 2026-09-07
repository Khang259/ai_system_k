"""Use case tests — state (fake NodeStateStore, no RTSP/model)."""
import asyncio

from domain.models import ResetStatus
from application.state.update_detection import UpdateDetection
from application.state.toggle_flag import ToggleFlag
from application.state.reset_flags import ResetFlagsByOrder
from application.state.get_all_points import GetAllPoints
from application.state.get_zone_state import GetZoneState
from tests.application.fakes import FakeNodeRepo, FakeNodeStateStore


def _run(coro):
    return asyncio.run(coro)


def test_update_detection_ok_and_not_ready():
    store = FakeNodeStateStore()
    uc = UpdateDetection(store)
    result = uc.execute("start_1", True)
    assert result.success
    assert "start_1" in store.snapshot_points()

    uc2 = UpdateDetection(FakeNodeStateStore(ready=False))
    assert not uc2.execute("start_1", True).success


def test_toggle_flag_ok_and_missing():
    store = FakeNodeStateStore()
    store.update_detection("start_1", True)
    uc = ToggleFlag(store)
    result = uc.execute("start_1")
    assert result.success
    assert result.data["flag"] is True

    missing = uc.execute("no_such")
    assert not missing.success


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


def test_get_all_points_and_zone_state():
    store = FakeNodeStateStore()
    store.update_detection("start_1", True)
    store.update_detection("end_1", False)

    points = GetAllPoints(store).execute()
    assert points.success
    assert "start_1" in points.data["points"]

    nodes = FakeNodeRepo()
    nodes.rows["start_1"] = {
        "node_id": "start_1",
        "zone_id": "AE5",
        "node_type": "start",
    }
    nodes.rows["end_1"] = {
        "node_id": "end_1",
        "zone_id": "AE5",
        "node_type": "end",
    }
    zone = _run(GetZoneState(store, nodes).execute("ae5"))
    assert zone.success
    assert zone.data["zone"] == "AE5"
    assert "start_1" in zone.data["nodes"]

    missing = _run(GetZoneState(store, nodes).execute("NOPE"))
    assert not missing.success
