from application.result import UseCaseResult
from application.ports import CameraRuntime, InferencePort
from application.scan_session import ScanSession


class StartZoneCameras:
    def __init__(self, cameras: CameraRuntime) -> None:
        self._cameras = cameras

    def execute(self, zone: str) -> UseCaseResult:
        if not self._cameras.is_ready():
            return UseCaseResult.fail("System not initialized")
        z = zone.upper()
        self._cameras.set_zone_enabled(z, True)
        enabled = self._cameras.get_status().get("enabled", 0)
        return UseCaseResult.ok(message=f"Zone {z} enabled", enabled=enabled)


class StopZoneCameras:
    def __init__(
        self, cameras: CameraRuntime, inference: InferencePort, scan: ScanSession
    ) -> None:
        self._cameras = cameras
        self._inference = inference
        self._scan = scan

    def execute(self, zone: str) -> UseCaseResult:
        if not self._cameras.is_ready():
            return UseCaseResult.fail("System not initialized")
        z = zone.upper()
        self._cameras.set_zone_enabled(z, False)
        enabled = self._cameras.get_status().get("enabled", 0)
        if enabled == 0:
            if self._inference.is_ready():
                self._inference.pause()
            self._scan.reset()
        return UseCaseResult.ok(message=f"Zone {z} disabled", enabled=enabled)
