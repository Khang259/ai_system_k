from application.result import UseCaseResult
from application.ports import CameraRuntime
from application.scan_session import ScanSession


class GetCameraStatus:
    def __init__(self, cameras: CameraRuntime, scan: ScanSession) -> None:
        self._cameras = cameras
        self._scan = scan

    def execute(self) -> UseCaseResult:
        if not self._cameras.is_ready():
            return UseCaseResult.fail("System not initialized")
        status = dict(self._cameras.get_status())
        batch = self._scan.get()
        status["batch"] = {
            "active": batch.active,
            "snapshot_size": batch.size,
            "dispatched": batch.sum_request,
            "remaining": max(0, batch.remaining),
        }
        return UseCaseResult.ok(**status)
