from application.result import UseCaseResult
from application.ports import NodeStateStore


class ToggleFlag:
    def __init__(self, state: NodeStateStore) -> None:
        self._state = state

    def execute(self, node_id: str) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")
        if not self._state.has_node(node_id):
            return UseCaseResult.fail("Node not found")
        new_flag = self._state.toggle_flag(node_id)
        return UseCaseResult.ok(node_id=node_id, flag=new_flag)
