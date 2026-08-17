from domain.models import ResetStatus
from application.result import UseCaseResult
from application.ports import NodeStateStore


class ResetFlagsByOrder:
    def __init__(self, state: NodeStateStore) -> None:
        self._state = state

    def execute(self, order_id: str, status: int) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")

        result = self._state.apply_reset(order_id, status)
        if not result.success:
            return UseCaseResult.fail(result.error or "Reset failed")

        data = {"message": result.message, "orderId": result.order_id}
        if status == ResetStatus.EMPTY_DONE or status == int(ResetStatus.EMPTY_DONE):
            data["reset_pairs"] = result.reset_pairs
        return UseCaseResult.ok(**data)
