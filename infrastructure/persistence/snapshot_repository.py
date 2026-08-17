"""Snapshot repository — collection: snapshots. FR-32→36."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from infrastructure.persistence.base_repository import BaseRepository, _now


class SnapshotRepository(BaseRepository):
    def __init__(self):
        super().__init__("snapshots")

    async def create(
        self,
        order_id: str,
        node_id: str,
        node_type: str,
        zone_id: str,
        decision: str,
        image_path: str,
    ) -> str:
        return await self.insert_one({
            "order_id": order_id,
            "node_id": node_id,
            "node_type": node_type,
            "zone_id": zone_id.upper(),
            "decision": decision,
            "image_path": image_path,
            "validation_result": "pending",
            "validated_at": None,
            "keep": False,
        })

    async def mark_validated(self, order_id: str, node_id: str, result: str) -> bool:
        keep = result == "false_positive"
        return await self.update_one(
            {"order_id": order_id, "node_id": node_id},
            {
                "validation_result": result,
                "validated_at": _now(),
                "keep": keep,
            },
        )

    async def get_false_positives(
        self,
        zone_id: Optional[str] = None,
        days: int = 7,
    ) -> List[Dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = {
            "validation_result": "false_positive",
            "created_at": {"$gte": since},
        }
        if zone_id:
            query["zone_id"] = zone_id.upper()
        return await self.find_many(query, sort=[("created_at", -1)])

    async def get_false_positive_rate(self, zone_id: Optional[str] = None) -> Dict:
        query = {"validation_result": {"$ne": "pending"}}
        if zone_id:
            query["zone_id"] = zone_id.upper()

        total = await self.count(query)
        fp_count = await self.count({**query, "validation_result": "false_positive"})

        return {
            "total": total,
            "false_positives": fp_count,
            "false_positive_rate": round(fp_count / total * 100, 2) if total else 0,
        }

    async def get_by_order(self, order_id: str) -> List[Dict]:
        return await self.find_many({"order_id": order_id})


snapshot_repository = SnapshotRepository()
