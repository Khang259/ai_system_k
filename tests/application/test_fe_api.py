"""Use case đợt 2/3 — cameras, ROI, nodes, zones, pairs."""
from __future__ import annotations

import asyncio

from application.fe_api.cameras import (
    CreateCamera,
    CreateRoi,
    DeleteCamera,
    DeleteRoi,
    GetCameras,
    GetRois,
    SetCameraStatus,
    UpdateCamera,
    UpdateRoi,
)
from application.fe_api.mappers import validate_box
from application.fe_api.nodes import (
    DeleteNode,
    GetNodes,
    SetMaintenance,
    UpdateNode,
)
from application.fe_api.pairs import (
    CreatePairFe,
    DeletePairFe,
    GetNodePairs,
    SetPairEnabledFe,
    UpdatePairFe,
    make_pair_id,
    parse_pair_id,
)
from application.fe_api.zones import GetZones
from tests.application.fakes import (
    FakeCameraConfigRepo,
    FakeCameraRuntime,
    FakeInference,
    FakeNodeRepo,
    FakeNodeStateStore,
    FakePairsRepo,
    FakeRuntimeControl,
    FakeZoneRepo,
)


def _run(coro):
    return asyncio.run(coro)


def _inf(paused: bool = True):
    return FakeInference(paused=paused)


def _update_camera(cams, nodes, pairs, runtime, state=None, inf=None):
    return UpdateCamera(
        cams,
        nodes,
        pairs,
        runtime,
        inf or _inf(),
        state or FakeNodeStateStore(),
        "640x480",
    )


def _roi_args(cams, nodes, pairs=None, inf=None):
    return (cams, nodes, 640, 480, inf or _inf(), pairs)


def _seed():
    cams = FakeCameraConfigRepo()
    nodes = FakeNodeRepo()
    zones = FakeZoneRepo()
    pairs = FakePairsRepo()
    runtime = FakeCameraRuntime(
        cameras=[
            {
                "cameraId": 1,
                "cam_id": "cam_0",
                "enabled": True,
                "streaming": True,
                "error": None,
            }
        ]
    )
    cams.items[1] = {
        "cameraId": 1,
        "name": "CAM-01",
        "url": "rtsp://x",
        "zone_id": "AE5",
        "enabled": True,
        "rois": {
            "start_10000060": {
                "roi": [80, 120, 140, 90],
                "start": True,
                "end": False,
            }
        },
    }
    nodes.rows["start_10000060"] = {
        "node_id": "start_10000060",
        "node_type": "start",
        "zone_id": "AE5",
        "camera_id": 1,
        "priority": 1,
        "enabled": True,
    }
    nodes.rows["end_10000760"] = {
        "node_id": "end_10000760",
        "node_type": "end",
        "zone_id": "AE5",
        "camera_id": 1,
        "priority": 1,
        "enabled": True,
    }
    zones.rows.append({"zone_id": "AE5", "name": "Khu AE5", "enabled": True})
    pairs.rows.append(
        {
            "start_point": "start_10000060",
            "end_point": "end_10000760",
            "zone_id": "AE5",
            "pair_type": "normal",
            "enabled": True,
        }
    )
    return cams, nodes, zones, pairs, runtime


def test_validate_box():
    assert validate_box([0, 0, 10, 10], 640, 480) is None
    assert validate_box([-1, 0, 10, 10], 640, 480)
    assert validate_box([600, 0, 50, 10], 640, 480)


def test_get_cameras_merges_runtime():
    cams, nodes, _, _, runtime = _seed()
    result = _run(GetCameras(cams, nodes, runtime, "640x480").execute())
    assert result.success
    item = result.data["items"][0]
    assert item["cameraId"] == 1
    assert item["rtspUrl"] == "rtsp://x"
    assert item["zone"] == "AE5"
    assert item["status"] == "streaming"
    assert item["observedNodeIds"] == ["start_10000060", "end_10000760"]
    assert item["mapPosition"] is None


def test_get_cameras_offline_when_runtime_down():
    cams, nodes, _, _, _ = _seed()
    runtime = FakeCameraRuntime(ready=False)
    result = _run(GetCameras(cams, nodes, runtime, "640x480").execute())
    assert result.data["items"][0]["status"] == "offline"


def test_get_rois_and_crud():
    cams, nodes, _, pairs, _ = _seed()
    get = GetRois(cams, nodes, 640, 480)
    listed = _run(get.execute())
    assert listed.data["items"][0]["id"] == "1:start_10000060"
    assert listed.data["items"][0]["box"] == [80, 120, 140, 90]
    assert listed.data["items"][0]["kind"] == "start"

    created = _run(
        CreateRoi(cams, nodes, 640, 480, _inf()).execute(
            1, "end_10000760", [10, 20, 30, 40]
        )
    )
    assert created.success
    assert created.data["id"] == "1:end_10000760"
    assert cams.items[1]["rois"]["end_10000760"]["ref_width"] == 640

    # Single (1 phần tử trong items) — tương thích cũ
    updated = _run(
        UpdateRoi(cams, nodes, 640, 480, _inf()).execute(
            [{"box": [11, 22, 33, 44], "id": "1:end_10000760"}]
        )
    )
    assert updated.success
    assert updated.data["items"][0]["box"] == [11.0, 22.0, 33.0, 44.0]

    # Batch — cập nhật 2 ROI cùng lúc
    batch = _run(
        UpdateRoi(cams, nodes, 640, 480, _inf()).execute(
            [
                {"id": "1:start_10000060", "box": [1, 2, 3, 4]},
                {"cameraId": 1, "nodeId": "end_10000760", "box": [5, 6, 7, 8]},
            ]
        )
    )
    assert batch.success
    assert len(batch.data["items"]) == 2
    assert cams.items[1]["rois"]["start_10000060"]["roi"] == [1.0, 2.0, 3.0, 4.0]
    assert cams.items[1]["rois"]["end_10000760"]["roi"] == [5.0, 6.0, 7.0, 8.0]

    # Batch fail trước khi ghi nếu 1 item không tồn tại
    bad = _run(
        UpdateRoi(cams, nodes, 640, 480, _inf()).execute(
            [
                {"id": "1:start_10000060", "box": [9, 9, 9, 9]},
                {"id": "1:missing_node", "box": [1, 1, 1, 1]},
            ]
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 404
    assert cams.items[1]["rois"]["start_10000060"]["roi"] == [1.0, 2.0, 3.0, 4.0]

    deleted = _run(
        DeleteRoi(cams, nodes, 640, 480, _inf(), pairs).execute(
            roi_id="1:end_10000760"
        )
    )
    assert deleted.success
    assert "end_10000760" not in cams.items[1]["rois"]
    assert deleted.data["pairsDeleted"] == ["start_10000060:end_10000760"]


def test_create_roi_rejects_bad_box():
    cams, nodes, _, _, _ = _seed()
    bad = _run(
        CreateRoi(cams, nodes, 640, 480, _inf()).execute(
            1, "start_10000060", [0, 0, 999, 10]
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 400


def test_set_camera_status_cascades():
    cams, nodes, _, pairs, runtime = _seed()
    result = _run(
        SetCameraStatus(
            cams, nodes, pairs, runtime, _inf(), FakeNodeStateStore()
        ).execute(1, False)
    )
    assert result.success
    assert cams.items[1]["enabled"] is False
    assert runtime.cameras[0]["enabled"] is False
    assert nodes.rows["start_10000060"]["enabled"] is False
    assert pairs.rows[0]["enabled"] is False
    assert result.data["nodesUpdated"] == 2
    assert result.data["pairsUpdated"] == 1


def test_get_nodes_and_maintenance():
    _, nodes, _, _, _ = _seed()
    state = FakeNodeStateStore()
    listed = _run(GetNodes(nodes).execute())
    assert len(listed.data["items"]) == 2
    assert listed.data["items"][0]["label"] == "S-01"
    assert listed.data["items"][0]["lock"] == {
        "user": False,
        "system": False,
        "orderId": None,
    }

    bad = _run(SetMaintenance(nodes, state).execute("start_10000060", True, ""))
    assert not bad.success

    ok = _run(
        SetMaintenance(nodes, state).execute(
            "start_10000060", True, "sửa camera"
        )
    )
    assert ok.success
    assert nodes.rows["start_10000060"]["is_under_maintenance"] is True
    after = _run(GetNodes(nodes).execute("AE5"))
    row = next(i for i in after.data["items"] if i["nodeId"] == "start_10000060")
    assert row["isUnderMaintenance"] is True
    assert row["maintenanceReason"] == "sửa camera"

    from application.fe_api.nodes import SetLock, Unlock

    locked = _run(SetLock(nodes, state).execute("start_10000060", user=True))
    assert locked.success
    assert locked.data["lock"]["user"] is True
    assert nodes.rows["start_10000060"]["lock"]["user"] is True

    # maintenance + lock cùng lúc
    row2 = _run(GetNodes(nodes).execute()).data["items"]
    start = next(i for i in row2 if i["nodeId"] == "start_10000060")
    assert start["isUnderMaintenance"] is True
    assert start["lock"]["user"] is True

    unlocked = _run(
        Unlock(nodes, state).execute("start_10000060", user=True, system=False)
    )
    assert unlocked.success
    assert unlocked.data["lock"]["user"] is False


def test_get_zones_is_running():
    cams, nodes, zones, _, runtime = _seed()
    result = _run(GetZones(zones, cams, nodes, runtime).execute())
    z = result.data["items"][0]
    assert z["id"] == "AE5"
    assert z["isRunning"] is True
    assert z["isStreaming"] is True
    assert z["cameraCount"] == 1
    assert z["nodeCount"] == 2


def test_get_zones_enabled_without_streaming():
    """start_all fail RTSP: công tắc bật nhưng chưa có frame."""
    cams, nodes, zones, _, runtime = _seed()
    runtime.cameras = [
        {
            "cameraId": 1,
            "cam_id": "cam_0",
            "enabled": True,
            "streaming": False,
            "error": "Timeout waiting for first frame",
        }
    ]
    result = _run(GetZones(zones, cams, nodes, runtime).execute())
    z = result.data["items"][0]
    assert z["isRunning"] is True
    assert z["isStreaming"] is False


def test_get_node_pairs_blocked_by_maintenance():
    _, nodes, _, pairs, _ = _seed()
    nodes.rows["start_10000060"]["is_under_maintenance"] = True
    nodes.rows["start_10000060"]["maintenance_reason"] = "bao tri"
    result = _run(GetNodePairs(pairs, nodes).execute())
    item = result.data["items"][0]
    assert item["isBlocked"] is True
    assert "bao tri" in item["blockedReason"]


def test_update_camera_partial_and_zone_cascade():
    cams, nodes, _, pairs, runtime = _seed()
    uc = _update_camera(cams, nodes, pairs, runtime)
    result = _run(
        uc.execute(1, name="NEW-NAME", rtsp_url="rtsp://new", zone="ae6")
    )
    assert result.success
    assert result.data["name"] == "NEW-NAME"
    assert result.data["rtspUrl"] == "rtsp://new"
    assert result.data["zone"] == "AE6"
    assert result.data["requiresRestart"] is True
    assert cams.items[1]["zone_id"] == "AE6"
    assert nodes.rows["start_10000060"]["zone_id"] == "AE6"
    assert nodes.rows["end_10000760"]["zone_id"] == "AE6"
    assert result.data["nodesZoneUpdated"] == 2


def test_update_camera_requires_field():
    cams, nodes, _, pairs, runtime = _seed()
    bad = _run(_update_camera(cams, nodes, pairs, runtime).execute(1))
    assert not bad.success
    assert bad.data["http_status"] == 400


def test_update_camera_observed_removes_cascade():
    cams, nodes, _, pairs, runtime = _seed()
    # Chỉ giữ end; gỡ start → xóa node + cascade pair + ROI
    result = _run(
        _update_camera(cams, nodes, pairs, runtime).execute(
            1, observed_node_ids=["end_10000760"]
        )
    )
    assert result.success
    assert result.data["observedNodeIds"] == ["end_10000760"]
    assert nodes.rows["end_10000760"]["camera_id"] == 1
    assert "start_10000060" not in nodes.rows
    assert "start_10000060" not in cams.items[1]["rois"]
    assert pairs.rows == []
    assert result.data["observedAssigned"] == 1
    assert result.data["observedRemoved"] == 1
    assert result.data["observedCreated"] == 0
    assert "start_10000060:end_10000760" in result.data["pairsDeleted"]


def test_update_camera_rejects_node_owned_by_other_camera():
    cams, nodes, _, pairs, runtime = _seed()
    nodes.rows["start_other"] = {
        "node_id": "start_other",
        "node_type": "start",
        "zone_id": "AE5",
        "camera_id": 99,
        "priority": 1,
        "enabled": True,
    }
    bad = _run(
        _update_camera(cams, nodes, pairs, runtime).execute(
            1, observed_node_ids=["start_10000060", "start_other"]
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 409


def test_update_camera_auto_creates_missing_nodes():
    cams, nodes, _, pairs, runtime = _seed()
    result = _run(
        _update_camera(cams, nodes, pairs, runtime).execute(
            1,
            observed_node_ids=[
                "start_10000060",
                "end_10000760",
                "start_10000999",
            ],
        )
    )
    assert result.success
    assert "start_10000999" in nodes.rows
    assert nodes.rows["start_10000999"]["camera_id"] == 1
    assert nodes.rows["start_10000999"]["node_type"] == "start"
    assert nodes.rows["start_10000999"]["zone_id"] == "AE5"
    assert result.data["observedCreated"] == 1
    assert set(result.data["observedNodeIds"]) == {
        "start_10000060",
        "end_10000760",
        "start_10000999",
    }

    bad = _run(
        _update_camera(cams, nodes, pairs, runtime).execute(
            1, observed_node_ids=["foo_123"]
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 400


def test_update_camera_blocked_when_inference_running():
    cams, nodes, _, pairs, runtime = _seed()
    bad = _run(
        _update_camera(
            cams, nodes, pairs, runtime, inf=_inf(paused=False)
        ).execute(1, name="X")
    )
    assert not bad.success
    assert bad.data["http_status"] == 409


def test_update_delete_node_cascades_pairs():
    cams, nodes, _, pairs, _ = _seed()
    state = FakeNodeStateStore()

    nodes.rows["start_10000099"] = {
        "node_id": "start_10000099",
        "node_type": "start",
        "zone_id": "AE5",
        "camera_id": 1,
        "priority": 3,
        "enabled": True,
        "is_under_maintenance": False,
        "maintenance_reason": "",
        "lock": {"user": False, "system": False, "orderId": None},
    }

    updated = _run(
        UpdateNode(nodes).execute("start_10000099", priority=5, enabled=False)
    )
    assert updated.success
    assert updated.data["priority"] == 5
    assert updated.data["enabled"] is False

    # Có pair → cascade xóa pair + node
    deleted = _run(
        DeleteNode(nodes, cams, pairs, state, _inf()).execute("start_10000060")
    )
    assert deleted.success
    assert deleted.data["roiDeleted"] is True
    assert "start_10000060:end_10000760" in deleted.data["pairsDeleted"]
    assert "start_10000060" not in nodes.rows
    assert "start_10000060" not in cams.items[1]["rois"]
    assert pairs.rows == []


def test_delete_camera_cascades():
    cams, nodes, _, pairs, _ = _seed()
    result = _run(
        DeleteCamera(
            cams, nodes, pairs, _inf(), FakeNodeStateStore()
        ).execute(1)
    )
    assert result.success
    assert 1 not in cams.items
    assert "start_10000060" not in nodes.rows
    assert "end_10000760" not in nodes.rows
    assert pairs.rows == []
    assert set(result.data["nodesDeleted"]) == {
        "start_10000060",
        "end_10000760",
    }


def test_create_camera_minimal():
    cams = FakeCameraConfigRepo()
    nodes = FakeNodeRepo()
    runtime = FakeCameraRuntime(ready=False)
    result = _run(
        CreateCamera(cams, nodes, runtime, _inf(), "640x480").execute(
            name="AE5-CAM-06",
            rtsp_url="rtsp://host/stream",
        )
    )
    assert result.success
    assert result.data["cameraId"] == 1
    assert result.data["name"] == "AE5-CAM-06"
    assert result.data["rtspUrl"] == "rtsp://host/stream"
    assert result.data["zone"] == ""
    assert result.data["observedNodeIds"] == []
    assert result.data["requiresRestart"] is False
    assert cams.items[1]["url"] == "rtsp://host/stream"


def test_create_camera_with_zone_and_nodes():
    cams, nodes, _, _, runtime = _seed()
    result = _run(
        CreateCamera(cams, nodes, runtime, _inf(), "640x480").execute(
            name="AE5-CAM-06",
            rtsp_url="rtsp://host/stream",
            zone="ae5",
            observed_node_ids=["start_10000099"],
        )
    )
    assert result.success
    assert result.data["cameraId"] == 2
    assert result.data["zone"] == "AE5"
    assert result.data["observedCreated"] == 1
    assert result.data["observedNodeIds"] == ["start_10000099"]
    assert result.data["requiresRestart"] is True
    assert nodes.rows["start_10000099"]["camera_id"] == 2


def test_create_camera_rejects_node_without_zone():
    cams = FakeCameraConfigRepo()
    nodes = FakeNodeRepo()
    bad = _run(
        CreateCamera(
            cams, nodes, FakeCameraRuntime(ready=False), _inf(), "640x480"
        ).execute(
            name="CAM",
            rtsp_url="rtsp://x",
            observed_node_ids=["start_1"],
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 400
    assert cams.items == {}


def test_create_camera_rejects_owned_node():
    cams, nodes, _, _, runtime = _seed()
    bad = _run(
        CreateCamera(cams, nodes, runtime, _inf(), "640x480").execute(
            name="CAM",
            rtsp_url="rtsp://x",
            zone="AE5",
            observed_node_ids=["start_10000060"],
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 409
    assert 2 not in cams.items


def test_create_camera_blocked_when_inference_running():
    cams = FakeCameraConfigRepo()
    nodes = FakeNodeRepo()
    bad = _run(
        CreateCamera(
            cams, nodes, FakeCameraRuntime(ready=False), _inf(paused=False), "640x480"
        ).execute(name="CAM", rtsp_url="rtsp://x")
    )
    assert not bad.success
    assert bad.data["http_status"] == 409


def test_create_camera_rejects_duplicate_rtsp():
    cams, nodes, _, _, runtime = _seed()
    bad = _run(
        CreateCamera(cams, nodes, runtime, _inf(), "640x480").execute(
            name="DUP",
            rtsp_url="rtsp://x",
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 409
    assert "camera 1" in (bad.error or "")
    assert 2 not in cams.items


def test_update_camera_rejects_duplicate_rtsp():
    cams, nodes, _, pairs, runtime = _seed()
    cams.items[2] = {
        "cameraId": 2,
        "name": "CAM-02",
        "url": "rtsp://other",
        "zone_id": "AE5",
        "enabled": True,
        "rois": {},
    }
    bad = _run(
        _update_camera(cams, nodes, pairs, runtime).execute(
            2, rtsp_url="rtsp://x"
        )
    )
    assert not bad.success
    assert bad.data["http_status"] == 409
    assert cams.items[2]["url"] == "rtsp://other"


def test_update_camera_allows_same_rtsp_on_self():
    cams, nodes, _, pairs, runtime = _seed()
    ok = _run(
        _update_camera(cams, nodes, pairs, runtime).execute(
            1, rtsp_url="rtsp://x", name="CAM-01-renamed"
        )
    )
    assert ok.success
    assert ok.data["rtspUrl"] == "rtsp://x"
    assert ok.data["name"] == "CAM-01-renamed"


def test_update_node_rejects_camera_id_change():
    _, nodes, _, _, _ = _seed()
    bad = _run(UpdateNode(nodes).execute("start_10000060", camera_id=2))
    assert not bad.success
    assert bad.data["http_status"] == 400


def test_parse_pair_id():
    assert parse_pair_id("start_a:end_b") == ("start_a", "end_b")
    assert parse_pair_id("start_a:_") == ("start_a", None)
    assert make_pair_id("start_a", "end_b") == "start_a:end_b"
    assert make_pair_id("start_a", None) == "start_a:_"


def test_pairs_crud_with_reload():
    cams, nodes, _, pairs, _ = _seed()
    runtime = FakeRuntimeControl()
    inf = _inf()
    nodes.rows["start_10000099"] = {
        "node_id": "start_10000099",
        "node_type": "start",
        "zone_id": "AE5",
        "camera_id": 1,
        "priority": 2,
        "enabled": True,
    }
    cams.items[1]["rois"]["start_10000099"] = {
        "roi": [1, 1, 10, 10],
        "start": True,
        "end": False,
    }
    cams.items[1]["rois"]["end_10000760"] = {
        "roi": [2, 2, 10, 10],
        "start": False,
        "end": True,
    }

    dup = _run(
        CreatePairFe(pairs, nodes, cams, runtime, inf).execute(
            "start_10000060",
            "AE5",
            end_node_id="end_10000760",
        )
    )
    assert not dup.success
    assert dup.data["http_status"] == 409

    # Xóa ROI end tạm → create pair mới phải 400
    del cams.items[1]["rois"]["end_10000760"]
    no_roi = _run(
        CreatePairFe(pairs, nodes, cams, runtime, inf).execute(
            "start_10000099",
            "AE5",
            end_node_id="end_10000760",
        )
    )
    assert not no_roi.success
    assert no_roi.data["http_status"] == 400
    assert "ROI" in no_roi.error

    cams.items[1]["rois"]["end_10000760"] = {
        "roi": [2, 2, 10, 10],
        "start": False,
        "end": True,
    }

    created = _run(
        CreatePairFe(pairs, nodes, cams, runtime, inf).execute(
            "start_10000099",
            "AE5",
            end_node_id="end_10000760",
            name="Test pair",
        )
    )
    assert created.success
    assert created.data["runtimeReloaded"] is True
    assert runtime.reloads == 1

    missing_end = _run(
        CreatePairFe(pairs, nodes, cams, runtime, inf).execute(
            "start_10000099",
            "AE5",
            pair_type="normal",
        )
    )
    assert not missing_end.success
    assert missing_end.data["http_status"] == 400

    pair_id = created.data["id"]
    updated = _run(
        UpdatePairFe(pairs, nodes, cams, runtime, inf).execute(
            pair_id, zone_id="AE6"
        )
    )
    assert updated.success
    assert updated.data["zoneId"] == "AE6"
    assert runtime.reloads == 2

    disabled = _run(
        SetPairEnabledFe(pairs, runtime, inf).execute(
            False, pair_id=updated.data["id"]
        )
    )
    assert disabled.success
    assert disabled.data["enabled"] is False

    deleted = _run(
        DeletePairFe(pairs, runtime, inf).execute(pair_id=updated.data["id"])
    )
    assert deleted.success
    assert runtime.reloads == 4
