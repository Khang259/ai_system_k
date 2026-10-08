from application.result import UseCaseResult
from application.ports import CameraRuntime, InferencePort
from infrastructure.sandbox.smoke_trail import emit


class StartScan:
    """Bật inference (YOLO/TRT) — detect ghi vào RAM. KHÔNG mở cổng gửi ICS."""

    def __init__(self, cameras: CameraRuntime, inference: InferencePort) -> None:
        self._cameras = cameras
        self._inference = inference

    def execute(self) -> UseCaseResult:
        if not self._cameras.is_ready() or not self._inference.is_ready():
            return UseCaseResult.fail("System not initialized")

        enabled = int(self._cameras.get_status().get("enabled", 0))
        if enabled == 0:
            return UseCaseResult.fail(
                "No cameras enabled. Call POST /api/v1/system/start_all first."
            )

        self._inference.resume()
        emit(
            "api",
            "start_scan",
            hint="Inference chạy — chờ start isReady rồi confirm-dispatch",
        )
        return UseCaseResult.ok(message="Scanning started")
