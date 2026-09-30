"""Map version repository — collection: map_versions (+ map_state singleton)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from infrastructure.persistence.base_repository import BaseRepository, _now


class MapVersionRepository(BaseRepository):
    def __init__(self):
        super().__init__("map_versions")

    async def insert_version(self, doc: Dict[str, Any]) -> str:
        return await self.insert_one(doc)

    async def get_by_version_id(self, version_id: str) -> Optional[Dict[str, Any]]:
        return await self.find_one({"version_id": version_id})

    async def list_newest_first(self) -> List[Dict[str, Any]]:
        return await self.find_many({}, sort=[("created_at", -1)])

    async def list_oldest_first(self) -> List[Dict[str, Any]]:
        return await self.find_many({}, sort=[("created_at", 1)])

    async def delete_by_version_id(self, version_id: str) -> bool:
        return await self.delete_one({"version_id": version_id})

    async def count_all(self) -> int:
        return await self.count({})


class MapStateRepository(BaseRepository):
    """Một document global: active_version_id."""

    STATE_ID = "global"

    def __init__(self):
        super().__init__("map_state")

    async def get_active_version_id(self) -> Optional[str]:
        doc = await self.find_one({"state_id": self.STATE_ID})
        if not doc:
            return None
        return doc.get("active_version_id")

    async def set_active_version_id(self, version_id: str) -> None:
        col = self._col()
        await col.update_one(
            {"state_id": self.STATE_ID},
            {
                "$set": {
                    "active_version_id": version_id,
                    "updated_at": _now(),
                },
                "$setOnInsert": {
                    "state_id": self.STATE_ID,
                    "created_at": _now(),
                },
            },
            upsert=True,
        )


map_version_repository = MapVersionRepository()
map_state_repository = MapStateRepository()
