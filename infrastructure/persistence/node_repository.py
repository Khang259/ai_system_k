"""Node repository — collection: nodes. Implements NodeRepositoryPort."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from infrastructure.persistence.base_repository import BaseRepository


class NodeRepository(BaseRepository):
    def __init__(self):
        super().__init__("nodes")

    async def get_by_zone(self, zone_id: str) -> List[Dict]:
        return await self.find_many(
            {"zone_id": zone_id.upper()},
            sort=[("node_type", 1), ("priority", 1)],
        )

    async def get_starts_by_zone(self, zone_id: str) -> List[Dict]:
        return await self.find_many(
            {"zone_id": zone_id.upper(), "node_type": "start", "enabled": True},
            sort=[("priority", 1)],
        )

    async def get_ends_by_zone(self, zone_id: str) -> List[Dict]:
        return await self.find_many(
            {"zone_id": zone_id.upper(), "node_type": "end", "enabled": True},
        )

    async def get_by_id(self, node_id: str) -> Optional[Dict]:
        return await self.find_one({"node_id": node_id})

    async def get_by_camera(self, camera_id: int) -> List[Dict]:
        return await self.find_many({"camera_id": camera_id})

    async def create(self, doc: Dict[str, Any]) -> str:
        return await self.insert_one(doc)

    async def set_enabled(self, node_id: str, enabled: bool) -> bool:
        return await self.update_one({"node_id": node_id}, {"enabled": enabled})

    async def set_camera_nodes_enabled(self, camera_id: int, enabled: bool) -> int:
        result = await self._col().update_many(
            {"camera_id": camera_id},
            {"$set": {"enabled": enabled}},
        )
        return result.modified_count

    async def update_priority(self, node_id: str, priority: int) -> bool:
        return await self.update_one({"node_id": node_id}, {"priority": priority})

    async def delete_by_node_id(self, node_id: str) -> bool:
        return await self.delete_one({"node_id": node_id})

    async def get_node_ids_by_zone(self, zone_id: str) -> Tuple[List[str], List[str]]:
        starts = await self.get_starts_by_zone(zone_id)
        ends = await self.get_ends_by_zone(zone_id)
        return (
            [s["node_id"] for s in starts],
            [e["node_id"] for e in ends],
        )


node_repository = NodeRepository()
