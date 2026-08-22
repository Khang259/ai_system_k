from application.cameras.preview import GetCameraPreview, GetCameraPreviewMeta
from tests.application.fakes import FakeCameraRuntime


def test_preview_ok():
    cams = FakeCameraRuntime()
    cams.preview_jpeg = b"\xff\xd8fake"
    result = GetCameraPreview(cams).execute(1, detect=True)
    assert result.success
    assert result.data["jpeg"] == b"\xff\xd8fake"


def test_preview_not_found():
    cams = FakeCameraRuntime()
    cams.preview_missing = True
    result = GetCameraPreview(cams).execute(99, detect=False)
    assert not result.success
    assert result.data["http_status"] == 404


def test_preview_runtime_down():
    cams = FakeCameraRuntime(ready=False)
    result = GetCameraPreview(cams).execute(1, detect=False)
    assert not result.success
    assert result.data["http_status"] == 503


def test_preview_meta_ok():
    cams = FakeCameraRuntime()
    cams.preview_meta = {
        "ts": 1.5,
        "w": 640,
        "h": 480,
        "rois": [{"roi": [1, 2, 3, 4], "node_id": "start_1"}],
        "dets": [{"cls": 0, "conf": 0.9, "xyxy": [10, 20, 30, 40]}],
    }
    result = GetCameraPreviewMeta(cams).execute(1)
    assert result.success
    assert result.data["w"] == 640
    assert result.data["dets"][0]["cls"] == 0


def test_preview_meta_not_found():
    cams = FakeCameraRuntime()
    cams.preview_missing = True
    result = GetCameraPreviewMeta(cams).execute(99)
    assert result.data["http_status"] == 404
