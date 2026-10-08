"""Use case tests — cameras + scan / dispatch batch."""
import asyncio

from application.scan_session import ScanSession
from application.cameras.start_stop import StartAllCameras, StopAllCameras
from application.cameras.zone import StartZoneCameras, StopZoneCameras
from application.cameras.confirm_dispatch import ConfirmDispatch
from application.cameras.pause_scan import PauseScan
from application.cameras.start_scan import StartScan
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


def test_start_scan_only_resumes_inference():
    cams = FakeCameraRuntime(enabled=0)
    inf = FakeInference()
    scan = ScanSession()
    assert not StartScan(cams, inf).execute().success

    cams.enabled = 2
    ok = StartScan(cams, inf).execute()
    assert ok.success
    assert inf.resume_calls == 1
    assert not scan.get().active  # cổng gửi ICS vẫn đóng


def _confirm(inf, state, scan, meta=None):
    return ConfirmDispatch(inf, state, scan, lambda: meta or {}).execute()


def test_confirm_dispatch_rejects_when_paused_or_nothing_ready():
    state = FakeNodeStateStore()
    scan = ScanSession()

    paused = _confirm(FakeInference(paused=True), state, scan)
    assert not paused.success
    assert paused.data["http_status"] == 409

    empty = _confirm(FakeInference(paused=False), state, scan)
    assert not empty.success
    assert empty.data["http_status"] == 409
    assert not scan.get().active


def test_confirm_dispatch_snapshots_ready_starts_sorted_by_priority():
    state = FakeNodeStateStore(
        validate_pairs=[["start_1", "end_1"], ["start_2", "end_1"], ["start_3", "end_1"]]
    )
    state._ns.ready_start_list.update({"start_1", "start_2"})
    state.update_detection("start_3", True)  # detected nhưng chưa isReady → không vào batch
    scan = ScanSession()
    meta = {"start_1": {"priority": 2}, "start_2": {"priority": 1}}

    ok = _confirm(FakeInference(paused=False), state, scan, meta)
    assert ok.success
    assert ok.data["batchNodes"] == ["start_2", "start_1"]
    assert scan.get().nodes == {"start_1", "start_2"}

    again = _confirm(FakeInference(paused=False), state, scan, meta)
    assert again.data["http_status"] == 409  # batch trước chưa xong


def test_pause_scan():
    inf = FakeInference(paused=False)
    scan = ScanSession()
    scan.start(["start_1"])
    result = PauseScan(inf, scan).execute()
    assert result.success
    assert inf.paused
    assert not scan.get().active


def test_on_dispatch_success_closes_gate_when_batch_complete():
    scan = ScanSession()
    scan.start(["start_1", "start_2"])

    OnDispatchSuccess(scan).execute("start_1")
    assert scan.get().active
    assert scan.get().dispatched == {"start_1"}

    OnDispatchSuccess(scan).execute("start_2")
    assert not scan.get().active
    assert scan.status()["stopReason"] == "batch_complete"


def test_cameras_not_initialized():
    cams = FakeCameraRuntime(ready=False)
    inf = FakeInference()
    assert not _run(StartAllCameras(cams, inf).execute()).success
    inf = FakeInference(ready=False)
    assert not PauseScan(inf, ScanSession()).execute().success
