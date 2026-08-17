from application.result import UseCaseResult
from application.ports import NodeStateStore


class UpdateDetection:
    def __init__(self, state: NodeStateStore) -> None:
        self._state = state

    def execute(self, node_id: str, detected: bool) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")
        self._state.update_detection(node_id, detected)
        return UseCaseResult.ok(message="Detection updated")
