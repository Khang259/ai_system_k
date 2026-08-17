"""Use case tests — camera config / nodes / pairs CRUD."""
import asyncio

from application.cameras_config.crud import (
    ListCameraConfigs,
    ListCameraConfigsByArea,
    CreateCameraConfig,
    UpdateCameraConfig,
    DeleteCameraConfig,
)
from application.nodes.crud import (
    GetNodesByZone,
    GetNodeById,
    SetNodeEnabled,
    UpdateNodePriority,
    CreateNode,
    DeleteNode,
)
from application.nodes.camera_nodes import DisableCameraNodes, EnableCameraNodes
from application.pairs.crud import GetPairsByZone, SetPairEnabled, CreatePair, DeletePair
from tests.application.fakes import (
    FakeCameraConfigRepo,
    FakeNodeRepo,
    FakeNodeStateStore,
    FakePairsRepo,
)


def _run(coro):
    return asyncio.run(coro)


def test_camera_config_crud():
    repo = FakeCameraConfigRepo()

    created = _run(CreateCameraConfig(repo).execute({"cameraId": 1, "zone_id": "AE5"}))
    assert created.success

    listed = _run(ListCameraConfigs(repo).execute())
    assert len(listed.data["items"]) == 1

    by_area = _run(ListCameraConfigsByArea(repo).execute("ae5"))
    assert by_area.data["area"] == "AE5"
    assert len(by_area.data["items"]) == 1

    updated = _run(UpdateCameraConfig(repo).execute(1, {"url": "rtsp://x"}))
    assert updated.success
    missing = _run(UpdateCameraConfig(repo).execute(99, {}))
    assert not missing.success

    deleted = _run(DeleteCameraConfig(repo).execute(1))
    assert deleted.success
    gone = _run(DeleteCameraConfig(repo).execute(1))
    assert not gone.success


def test_node_crud_and_enable():
    repo = FakeNodeRepo()
    state = FakeNodeStateStore()
    state._ns.ready_start_list.add("start_1")

    missing_fields = _run(CreateNode(repo).execute({"node_id": "x"}))
    assert not missing_fields.success

    bad_type = _run(
        CreateNode(repo).execute(
            {"node_id": "start_1", "node_type": "mid", "zone_id": "AE5", "camera_id": 1}
        )
    )
    assert not bad_type.success

    created = _run(
        CreateNode(repo).execute(
            {"node_id": "start_1", "node_type": "start", "zone_id": "AE5", "camera_id": 1}
        )
    )
    assert created.success

    by_id = _run(GetNodeById(repo).execute("start_1"))
    assert by_id.success
    assert not _run(GetNodeById(repo).execute("nope")).success

    by_zone = _run(GetNodesByZone(repo).execute("ae5"))
    assert len(by_zone.data["nodes"]) == 1

    pri_bad = _run(UpdateNodePriority(repo).execute("start_1", -1))
    assert not pri_bad.success
    pri_ok = _run(UpdateNodePriority(repo).execute("start_1", 3))
    assert pri_ok.data["priority"] == 3

    disabled = _run(SetNodeEnabled(repo, state).execute("start_1", False))
    assert disabled.success
    assert "start_1" not in state._ns.ready_start_list

    deleted = _run(DeleteNode(repo).execute("start_1"))
    assert deleted.success


def test_disable_enable_camera_nodes():
    repo = FakeNodeRepo()
    state = FakeNodeStateStore()
    repo.rows["start_1"] = {"node_id": "start_1", "camera_id": 7, "enabled": True}
    state._ns.ready_start_list.add("start_1")

    disabled = _run(DisableCameraNodes(repo, state).execute(7))
    assert disabled.data["nodes_disabled"] == 1
    assert "start_1" not in state._ns.ready_start_list

    enabled = _run(EnableCameraNodes(repo).execute(7))
    assert enabled.data["nodes_enabled"] == 1


def test_pairs_crud():
    repo = FakePairsRepo()

    missing = _run(CreatePair(repo).execute({"start_point": "s"}))
    assert not missing.success
    bad_type = _run(
        CreatePair(repo).execute(
            {"start_point": "s", "zone_id": "AE5", "pair_type": "x"}
        )
    )
    assert not bad_type.success
    no_end = _run(
        CreatePair(repo).execute(
            {"start_point": "s", "zone_id": "AE5", "pair_type": "normal"}
        )
    )
    assert not no_end.success

    created = _run(
        CreatePair(repo).execute(
            {
                "start_point": "start_1",
                "end_point": "end_1",
                "zone_id": "AE5",
                "pair_type": "normal",
            }
        )
    )
    assert created.success

    empty = _run(
        CreatePair(repo).execute(
            {"start_point": "start_e", "zone_id": "AE5", "pair_type": "empty"}
        )
    )
    assert empty.success

    listed = _run(GetPairsByZone(repo).execute("ae5"))
    assert len(listed.data["pairs"]) == 2

    enabled = _run(SetPairEnabled(repo).execute("start_1", "end_1", False))
    assert enabled.success
    assert not _run(SetPairEnabled(repo).execute("x", "y", True)).success

    deleted = _run(DeletePair(repo).execute("start_1", "end_1"))
    assert deleted.success
