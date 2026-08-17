from application.result import UseCaseResult
from application.ports import NodeStateStore


class GetAllPoints:
    def __init__(self, state: NodeStateStore) -> None:
        self._state = state

    def execute(self) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")
        return UseCaseResult.ok(points=self._state.snapshot_points())
