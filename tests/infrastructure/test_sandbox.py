"""Sandbox runtime — camera giả phải hành xử giống camera thật (pause / enabled / ROI)."""
from __future__ import annotations

import pytest

pytest.importorskip("torch")

from application.dispatch.dispatch_service import DispatchService
from domain.models import OrderStatus
from domain.node_state import NodeState
from infrastructure.adapters import NodeStateAdapter
from infrastructure.sandbox import SandboxCameraManager, SandboxIcs, SandboxInference

ROI = {"roi": [0, 0, 10, 10]}
CAMERAS = [
    {"cameraId": 1, "zone_id": "A", "rois": {
        "start_1001": ROI, "start_1002": ROI, "start_1003": ROI,
    }},
    {"cameraId": 2, "zone_id": "B", "rois": {"end_2001": ROI}},
]
PAIRS = [
    ("start_1001", "end_2001"),
    ("start_1002", "end_2001"),
    ("start_1003", "end_2001"),
]


@pytest.fixture
def clock():
    return [0.0]


@pytest.fixture
def node_state(clock):
    return NodeState(
        PAIRS, start_ready_after_sec=1, end_ready_after_sec=1, time_fn=lambda: clock[0]
    )


@pytest.fixture
def inference():
    return SandboxInference()


@pytest.fixture
def cameras(node_state, inference):
    mgr = SandboxCameraManager(
        cameras_config=CAMERAS, state_manager=node_state, inference_engine=inference
    )
    mgr.start_all_cameras()
    return mgr


def test_paused_inference_emits_nothing(cameras, node_state):
    cameras.set_node_state("start_1001", True)
    cameras.tick()  # SandboxInference mặc định pause như engine thật
    assert "start_1001" not in node_state.points


def test_resumed_inference_pushes_desired_state(cameras, node_state, inference):
    inference.resume()
    cameras.set_node_state("start_1001", True)
    cameras.tick()
    assert node_state.points["start_1001"]["state"] is True
    assert node_state.points["end_2001"]["state"] is False


def test_disabled_camera_emits_nothing(cameras, node_state, inference):
    inference.resume()
    cameras.set_camera_enabled_by_id(1, False)
    cameras.set_node_state("start_1001", True)
    cameras.tick()
    assert "start_1001" not in node_state.points
    assert "end_2001" in node_state.points


def test_unknown_node_is_rejected(cameras):
    assert cameras.set_node_state("start_9999", True) is False
    assert all(item["nodeId"] != "start_9999" for item in cameras.get_node_states())


def test_status_reports_enabled_cameras_as_streaming(cameras):
    cameras.set_camera_enabled_by_id(2, False)
    status = cameras.get_status()
    assert status["total"] == 2
    assert status["streaming"] == 1


def test_sandbox_ics_records_order_and_status():
    ics = SandboxIcs()
    assert ics.send({"orderId": "S-1-2-x", "taskOrderDetail": [{"taskPath": "1,2"}]})
    assert ics.get_orders()[0]["seq"] == 1
    assert ics.set_status("S-1-2-x", OrderStatus.RUNNING)
    assert ics.get_order_list(1) == [{"OrderId": "S-1-2-x", "OrderStatus": 6}]
    assert ics.set_status("missing", 3) is False


def test_dispatch_follows_priority_with_single_end(cameras, node_state, inference, clock):
    """3 start cùng có hàng, 1 end → lệnh lần lượt theo priority ASC."""
    start_meta = {
        "start_1001": {"priority": 3, "zone_id": "A"},
        "start_1002": {"priority": 1, "zone_id": "A"},
        "start_1003": {"priority": 2, "zone_id": "A"},
    }
    ics = SandboxIcs()
    service = DispatchService(ics, start_meta=start_meta)
    state = NodeStateAdapter(node_state)

    inference.resume()
    for node_id in start_meta:
        cameras.set_node_state(node_id, True)

    dispatched = []
    for _ in range(3):
        cameras.tick()
        clock[0] += 2
        state.process_starts()
        state.process_ends()
        sent, _ = service.dispatch_single(service.build_pairs(state), state)
        assert len(sent) == 1, "1 end → mỗi vòng đúng 1 lệnh"
        order = sent[0]
        dispatched.append(order["start"])

        # Xe lấy hàng đi → start trống, rồi ICS báo xong (3) → gỡ lock
        cameras.set_node_state(order["start"], False)
        cameras.tick()
        state.apply_reset(order["orderId"], OrderStatus.CANCELED)

    assert dispatched == ["start_1002", "start_1003", "start_1001"]
