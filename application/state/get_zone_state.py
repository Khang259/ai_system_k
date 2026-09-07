from application.result import UseCaseResult
from application.ports import NodeRepositoryPort, NodeStateStore


class GetZoneState:
    def __init__(self, state: NodeStateStore, nodes: NodeRepositoryPort) -> None:
        self._state = state
        self._nodes = nodes

    async def execute(self, zone: str) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")

        docs = await self._nodes.get_by_zone(zone.upper())
        node_ids = {d["node_id"] for d in docs if d.get("node_id")}
        if not node_ids:
            return UseCaseResult.fail("Zone not found")

        snapshot = self._state.snapshot_points()
        nodes = {nid: snapshot[nid] for nid in node_ids if nid in snapshot}
        return UseCaseResult.ok(zone=zone.upper(), nodes=nodes)
