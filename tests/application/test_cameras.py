"""Use case tests — cameras + scan session."""
import asyncio

from application.scan_session import ScanSession
from application.cameras.start_stop import StartAllCameras, StopAllCameras
from application.cameras.zone import StartZoneCameras, StopZoneCameras
from application.cameras.get_status import GetCameraStatus
from application.cameras.confirm_ready import ConfirmReady
from application.cameras.pause_scan import PauseScan
from application.cameras.on_dispatch_success import OnDispatchSuccess
from tests.application.fakes import FakeCameraRuntime, FakeInference, FakeNodeStateStore


def _run(coro):
    return asyncio.run(coro)


def test_start_stop_all_cameras():
    cams = FakeCameraRuntime(enabled=0)
    inf = FakeInference()
    scan = ScanSession()
    started = _run(StartAllCameras(cams, inf, wait_stream_sec=1).execute())
    assert started.success
    assert cams.started_all
    assert started.data["streaming"] >= 1
    assert started.data["warnings"]
    stop = StopAllCameras(cams, inf, scan).execute()
    assert stop.success
    assert cams.stopped_all
    assert inf.pause_calls == 1


def test_start_all_fails_when_model_missing():
    cams = FakeCameraRuntime()
    inf = FakeInference(model_loaded=False, load_error="engine not found")
    result = _run(StartAllCameras(cams, inf, wait_model_sec=0.1).execute())
    assert not result.success
    assert "Model not loaded" in result.error
    assert not cams.started_all


def test_start_all_fails_when_no_camera_streaming():
    cams = FakeCameraRuntime(
        enabled=0,
        streaming=0,
        auto_stream=False,
        cameras=[
            {
                "cam_id": "cam_0",
                "enabled": True,
                "streaming": False,
                "error": "Timeout waiting for first frame",
            }
        ],
    )
    inf = FakeInference()
    result = _run(StartAllCameras(cams, inf, wait_stream_sec=0.3).execute())
    assert not result.success
    assert "No camera streaming" in result.error
    assert cams.started_all


def test_start_stop_zone():
    cams = FakeCameraRuntime()
    inf = FakeInference()
    scan = ScanSession()
    start = StartZoneCameras(cams).execute("ae5")
    assert start.success
    assert start.data["enabled"] == 1
    assert cams.zone_calls == [("AE5", True)]

    stop = StopZoneCameras(cams, inf, scan).execute("ae5")
    assert stop.success
    assert inf.pause_calls == 1


def test_confirm_ready_requires_enabled_cameras():
    cams = FakeCameraRuntime(enabled=0)
    inf = FakeInference()
    state = FakeNodeStateStore()
    scan = ScanSession()
    fail = ConfirmReady(cams, inf, state, scan).execute()
    assert not fail.success

    cams.enabled = 2
    state.update_detection("start_1", True)
    ok = ConfirmReady(cams, inf, state, scan).execute()
    assert ok.success
    assert ok.data["snapshot_size"] == 1
    assert inf.resume_calls == 1
    assert scan.get().active


def test_pause_scan():
    inf = FakeInference(paused=False)
    scan = ScanSession()
    scan.start(["start_1"])
    result = PauseScan(inf, scan).execute()
    assert result.success
    assert inf.paused
    assert not scan.get().active


def test_get_camera_status_includes_batch():
    cams = FakeCameraRuntime()
    scan = ScanSession()
    scan.start(["a", "b"])
    result = GetCameraStatus(cams, scan).execute()
    assert result.success
    assert result.data["enabled"] == 1
    assert result.data["batch"]["snapshot_size"] == 2


def test_on_dispatch_success_auto_pause_and_new_nodes():
    inf = FakeInference(paused=False)
    state = FakeNodeStateStore()
    scan = ScanSession()
    scan.start(["start_1"])
    OnDispatchSuccess(inf, state, scan).execute("start_1")
    assert inf.pause_calls == 1
    assert not scan.get().active

    inf2 = FakeInference(paused=False)
    state2 = FakeNodeStateStore()
    state2.update_detection("start_1", True)
    state2.update_detection("start_99", True)
    scan2 = ScanSession()
    scan2.start(["start_1", "start_2"])
    OnDispatchSuccess(inf2, state2, scan2).execute("start_1")
    assert inf2.pause_calls == 1
    assert not scan2.get().active


def test_cameras_not_initialized():
    cams = FakeCameraRuntime(ready=False)
    inf = FakeInference()
    assert not _run(StartAllCameras(cams, inf).execute()).success
    inf = FakeInference(ready=False)
    assert not PauseScan(inf, ScanSession()).execute().success
