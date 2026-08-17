from application.result import UseCaseResult
from application.ports import NodeRepositoryPort, NodeStateStore


class DisableCameraNodes:
    def __init__(self, repo: NodeRepositoryPort, state: NodeStateStore) -> None:
        self._repo = repo
        self._state = state

    async def execute(self, camera_id: int) -> UseCaseResult:
        count = await self._repo.set_camera_nodes_enabled(camera_id, False)
        if self._state.is_ready():
            nodes = await self._repo.get_by_camera(camera_id)
            for node in nodes:
                self._state.discard_from_ready(node["node_id"])
        return UseCaseResult.ok(camera_id=camera_id, nodes_disabled=count)


class EnableCameraNodes:
    def __init__(self, repo: NodeRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, camera_id: int) -> UseCaseResult:
        count = await self._repo.set_camera_nodes_enabled(camera_id, True)
        return UseCaseResult.ok(camera_id=camera_id, nodes_enabled=count)
