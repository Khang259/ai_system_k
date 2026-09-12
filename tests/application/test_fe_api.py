"""Use case đợt 2/3 — cameras, ROI, nodes, zones, pairs."""
from __future__ import annotations

import asyncio

from application.fe_api.cameras import (
    CreateRoi,
    DeleteRoi,
    GetCameras,
    GetRois,
    SetCameraStatus,
    UpdateRoi,
)
from application.fe_api.mappers import validate_box
from application.fe_api.nodes import GetNodes, SetMaintenance
from application.fe_api.pairs import GetNodePairs
from application.fe_api.zones import GetZones
from tests.application.fakes import (
    FakeCameraConfigRepo,
    FakeCameraRuntime,
    FakeNodeRepo,
    FakeNodeStateStore,
    FakePairsRepo,
    FakeZoneRepo,
)


def _run(coro):
    return asyncio.run(coro)


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
    cams, nodes, _, _, _ = _seed()
    get = GetRois(cams, nodes, 640, 480)
    listed = _run(get.execute())
    assert listed.data["items"][0]["id"] == "1:start_10000060"
    assert listed.data["items"][0]["box"] == [80, 120, 140, 90]
    assert listed.data["items"][0]["kind"] == "start"

    created = _run(
        CreateRoi(cams, nodes, 640, 480).execute(
            1, "end_10000760", [10, 20, 30, 40]
        )
    )
    assert created.success
    assert created.data["id"] == "1:end_10000760"
    assert cams.items[1]["rois"]["end_10000760"]["ref_width"] == 640

    updated = _run(
        UpdateRoi(cams, nodes, 640, 480).execute(
            box=[11, 22, 33, 44], roi_id="1:end_10000760"
        )
    )
    assert updated.success
    assert updated.data["box"] == [11.0, 22.0, 33.0, 44.0]

    deleted = _run(DeleteRoi(cams, nodes, 640, 480).execute(roi_id="1:end_10000760"))
    assert deleted.success
    assert "end_10000760" not in cams.items[1]["rois"]


def test_create_roi_rejects_bad_box():
    cams, nodes, _, _, _ = _seed()
    bad = _run(CreateRoi(cams, nodes, 640, 480).execute(1, "start_10000060", [0, 0, 999, 10]))
    assert not bad.success
    assert bad.data["http_status"] == 400


def test_set_camera_status_syncs_runtime():
    cams, nodes, _, _, runtime = _seed()
    result = _run(SetCameraStatus(cams, runtime).execute(1, False))
    assert result.success
    assert cams.items[1]["enabled"] is False
    assert runtime.cameras[0]["enabled"] is False


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
    assert z["cameraCount"] == 1
    assert z["nodeCount"] == 2


def test_get_node_pairs_blocked_by_maintenance():
    _, nodes, _, pairs, _ = _seed()
    nodes.rows["start_10000060"]["is_under_maintenance"] = True
    nodes.rows["start_10000060"]["maintenance_reason"] = "bao tri"
    result = _run(GetNodePairs(pairs, nodes).execute())
    item = result.data["items"][0]
    assert item["isBlocked"] is True
    assert "bao tri" in item["blockedReason"]
