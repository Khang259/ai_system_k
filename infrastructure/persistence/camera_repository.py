"""Camera repository — collection: cameras. Implements CameraConfigRepository Port."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from infrastructure.persistence.base_repository import BaseRepository


class CameraRepository(BaseRepository):
    def __init__(self):
        super().__init__("cameras")

    async def get_all(self) -> List[Dict]:
        return await self.find_many({})

    async def get_by_area(self, area: str) -> List[Dict[str, Any]]:
        return await self.find_many({"zone_id": area.upper()})

    async def get_by_zone(self, zone_id: str) -> List[Dict]:
        return await self.find_many({"zone_id": zone_id.upper(), "enabled": True})

    async def get_by_id(self, camera_id: int) -> Optional[Dict]:
        return await self.find_one({"cameraId": camera_id})

    async def create(self, doc: Dict[str, Any]) -> str:
        return await self.insert_one(doc)

    async def update_by_camera_id(self, camera_id: int, data: Dict[str, Any]) -> bool:
        return await self.update_one({"cameraId": camera_id}, data)

    async def delete_by_camera_id(self, camera_id: int) -> bool:
        return await self.delete_one({"cameraId": camera_id})

    async def set_enabled(self, camera_id: int, enabled: bool) -> bool:
        return await self.update_one({"cameraId": camera_id}, {"enabled": enabled})

    async def set_zone_enabled(self, zone_id: str, enabled: bool) -> int:
        result = await self._col().update_many(
            {"zone_id": zone_id.upper()},
            {"$set": {"enabled": enabled}},
        )
        return result.modified_count

    async def update_roi(self, camera_id: int, node_id: str, bbox: list) -> bool:
        return await self.update_one(
            {"cameraId": camera_id},
            {f"rois.{node_id}": bbox},
        )


camera_repository = CameraRepository()
