"""Pairs repository — collection: pairs. Implements PairsRepositoryPort."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from infrastructure.persistence.base_repository import BaseRepository


class PairsRepository(BaseRepository):
    def __init__(self):
        super().__init__("pairs")

    async def get_all(self) -> List[Dict]:
        """Runtime: chỉ pair enabled. FE dùng `list_all` để thấy cả disabled."""
        return await self.find_many({"enabled": True})

    async def list_all(self) -> List[Dict]:
        return await self.find_many({})

    async def get_by_zone(self, zone_id: str) -> List[Dict[str, Any]]:
        return await self.find_many({"zone_id": zone_id.upper()})

    async def get_as_tuples(self) -> List[Tuple]:
        docs = await self.get_all()
        result = []
        for doc in docs:
            if doc["pair_type"] == "empty":
                result.append((doc["start_point"],))
            else:
                result.append((doc["start_point"], doc["end_point"]))
        return result

    async def get_by_start(self, start_point: str) -> List[Dict]:
        return await self.find_many({"start_point": start_point, "enabled": True})

    async def create(self, doc: Dict[str, Any]) -> str:
        return await self.insert_one(doc)

    async def set_enabled(
        self, start_point: str, end_point: Optional[str], enabled: bool
    ) -> bool:
        query: Dict[str, Any] = {"start_point": start_point, "end_point": end_point}
        return await self.update_one(query, {"enabled": enabled})

    async def delete(self, start_point: str, end_point: Optional[str]) -> bool:
        query = {"start_point": start_point}
        if end_point:
            query["end_point"] = end_point
        else:
            query["end_point"] = None
        return await self.delete_one(query)

    async def find_by_key(
        self, start_point: str, end_point: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        query: Dict[str, Any] = {"start_point": start_point, "end_point": end_point}
        return await self.find_one(query)

    async def update_by_key(
        self,
        start_point: str,
        end_point: Optional[str],
        data: Dict[str, Any],
    ) -> bool:
        query: Dict[str, Any] = {"start_point": start_point, "end_point": end_point}
        return await self.update_one(query, data)

    async def list_containing_node(self, node_id: str) -> List[Dict[str, Any]]:
        """Pair có node làm start hoặc end — dùng chặn xóa node."""
        if not node_id:
            return []
        return await self.find_many(
            {
                "$or": [
                    {"start_point": node_id},
                    {"end_point": node_id},
                ]
            }
        )


pairs_repository = PairsRepository()
