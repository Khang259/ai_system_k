from application.result import UseCaseResult
from application.ports import CameraRuntime


class GetCameraPreview:
    """JPEG RAM: raw RTSP-frame hoặc overlay ROI+bbox+conf."""

    def __init__(self, cameras: CameraRuntime) -> None:
        self._cameras = cameras

    def execute(self, camera_id: int, detect: bool) -> UseCaseResult:
        if not self._cameras.is_ready():
            return UseCaseResult.fail("Runtime not started", http_status=503)
        jpeg, error, status = self._cameras.get_preview_jpeg(int(camera_id), detect)
        if jpeg is not None:
            return UseCaseResult.ok(jpeg=jpeg)
        return UseCaseResult.fail(error or "No preview", http_status=status)


class GetCameraPreviewMeta:
    """JSON ROI + dets + ts (không gian infer W×H) cho canvas F5."""

    def __init__(self, cameras: CameraRuntime) -> None:
        self._cameras = cameras

    def execute(self, camera_id: int) -> UseCaseResult:
        if not self._cameras.is_ready():
            return UseCaseResult.fail("Runtime not started", http_status=503)
        meta, error, status = self._cameras.get_preview_meta(int(camera_id))
        if meta is not None:
            return UseCaseResult.ok(**meta)
        return UseCaseResult.fail(error or "No preview meta", http_status=status)
