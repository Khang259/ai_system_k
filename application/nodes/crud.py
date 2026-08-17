from typing import Any, Dict

from application.result import UseCaseResult
from application.ports import NodeRepositoryPort, NodeStateStore


class GetNodesByZone:
    def __init__(self, repo: NodeRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, zone_id: str) -> UseCaseResult:
        nodes = await self._repo.get_by_zone(zone_id)
        return UseCaseResult.ok(zone_id=zone_id.upper(), nodes=nodes)


class GetNodeById:
    def __init__(self, repo: NodeRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, node_id: str) -> UseCaseResult:
        node = await self._repo.get_by_id(node_id)
        if not node:
            return UseCaseResult.fail(f"Node {node_id} not found")
        return UseCaseResult.ok(node=node)


class SetNodeEnabled:
    def __init__(self, repo: NodeRepositoryPort, state: NodeStateStore) -> None:
        self._repo = repo
        self._state = state

    async def execute(self, node_id: str, enabled: bool) -> UseCaseResult:
        ok = await self._repo.set_enabled(node_id, enabled)
        if not ok:
            return UseCaseResult.fail(f"Node {node_id} not found")
        if self._state.is_ready() and not enabled:
            self._state.discard_from_ready(node_id)
        return UseCaseResult.ok(node_id=node_id, enabled=enabled)


class UpdateNodePriority:
    def __init__(self, repo: NodeRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, node_id: str, priority: int) -> UseCaseResult:
        if priority < 0:
            return UseCaseResult.fail("Priority must be >= 0")
        ok = await self._repo.update_priority(node_id, priority)
        if not ok:
            return UseCaseResult.fail(f"Node {node_id} not found")
        return UseCaseResult.ok(node_id=node_id, priority=priority)


class CreateNode:
    def __init__(self, repo: NodeRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, doc: Dict[str, Any]) -> UseCaseResult:
        required = {"node_id", "node_type", "zone_id", "camera_id"}
        missing = required - set(doc.keys())
        if missing:
            return UseCaseResult.fail(f"Missing fields: {missing}")
        if doc["node_type"] not in ("start", "end"):
            return UseCaseResult.fail("node_type must be 'start' or 'end'")
        payload = dict(doc)
        payload.setdefault("priority", 999)
        payload.setdefault("enabled", True)
        inserted_id = await self._repo.create(payload)
        return UseCaseResult.ok(inserted_id=inserted_id)


class DeleteNode:
    def __init__(self, repo: NodeRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, node_id: str) -> UseCaseResult:
        ok = await self._repo.delete_by_node_id(node_id)
        if not ok:
            return UseCaseResult.fail(f"Node {node_id} not found")
        return UseCaseResult.ok(node_id=node_id)
