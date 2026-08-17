"""Zone repository — collection: zones"""
from __future__ import annotations

from typing import Dict, List, Optional

from infrastructure.persistence.base_repository import BaseRepository


class ZoneRepository(BaseRepository):
    def __init__(self):
        super().__init__("zones")

    async def get_all(self) -> List[Dict]:
        return await self.find_many({})

    async def get_by_id(self, zone_id: str) -> Optional[Dict]:
        return await self.find_one({"zone_id": zone_id.upper()})

    async def create(self, zone_id: str, name: str) -> str:
        return await self.insert_one({
            "zone_id": zone_id.upper(),
            "name": name,
            "enabled": True,
        })

    async def set_enabled(self, zone_id: str, enabled: bool) -> bool:
        return await self.update_one(
            {"zone_id": zone_id.upper()},
            {"enabled": enabled},
        )

    async def is_enabled(self, zone_id: str) -> bool:
        doc = await self.find_one({"zone_id": zone_id.upper()})
        return doc.get("enabled", False) if doc else False


zone_repository = ZoneRepository()
