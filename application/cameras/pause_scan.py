from application.result import UseCaseResult
from application.ports import InferencePort
from application.scan_session import ScanSession


class PauseScan:
    def __init__(self, inference: InferencePort, scan: ScanSession) -> None:
        self._inference = inference
        self._scan = scan

    def execute(self) -> UseCaseResult:
        if not self._inference.is_ready():
            return UseCaseResult.fail("System not initialized")
        self._inference.pause()
        self._scan.reset()
        return UseCaseResult.ok(message="Scanning paused")
