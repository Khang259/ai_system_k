from application.result import UseCaseResult
from application.ports import CameraRuntime, InferencePort, NodeStateStore
from application.scan_session import ScanSession


class ConfirmReady:
    def __init__(
        self,
        cameras: CameraRuntime,
        inference: InferencePort,
        state: NodeStateStore,
        scan: ScanSession,
    ) -> None:
        self._cameras = cameras
        self._inference = inference
        self._state = state
        self._scan = scan

    def execute(self) -> UseCaseResult:
        if not self._cameras.is_ready() or not self._inference.is_ready():
            return UseCaseResult.fail("System not initialized")

        enabled = int(self._cameras.get_status().get("enabled", 0))
        if enabled == 0:
            return UseCaseResult.fail(
                "No cameras enabled. Call POST /cameras/start-all first."
            )

        detected = self._state.get_detected_start_nodes() if self._state.is_ready() else set()
        batch = self._scan.start(detected)
        self._inference.resume()
        return UseCaseResult.ok(
            message="Scanning started",
            snapshot_size=batch.size,
            snapshot_nodes=list(batch.nodes),
        )
