from application.result import UseCaseResult
from application.ports import NodeStateStore


class ResetFlagsByOrder:
    def __init__(self, state: NodeStateStore) -> None:
        self._state = state

    def execute(self, order_id: str, status: int) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")

        result = self._state.apply_reset(order_id, status)
        if result.success:
            return UseCaseResult.ok(message=result.message, orderId=result.order_id)

        # Sau restart: order_mapping RAM trống nhưng Mongo/RAM hydrate còn system lock
        cleared = []
        if hasattr(self._state, "clear_system_by_order_id"):
            cleared = self._state.clear_system_by_order_id(order_id) or []
        if cleared:
            return UseCaseResult.ok(
                message=f"System lock cleared for orderId {order_id}",
                orderId=order_id,
                reset_pairs=[[n] for n in cleared],
            )

        return UseCaseResult.fail(result.error or "Reset failed")
