"""Dispatch log repository — collection: dispatch_logs"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from infrastructure.persistence.base_repository import BaseRepository, _now


class DispatchLogRepository(BaseRepository):
    def __init__(self):
        super().__init__("dispatch_logs")

    async def create(self, doc: Dict) -> str:
        return await self.insert_one(doc)

    async def mark_completed(self, order_id: str) -> bool:
        completed_at = _now()
        doc = await self.find_one({"order_id": order_id})
        if not doc:
            return False

        dispatched_at = doc.get("dispatched_at")
        duration = None
        if dispatched_at:
            duration = int((completed_at - dispatched_at).total_seconds())

        return await self.update_one(
            {"order_id": order_id},
            {"status": "success", "completed_at": completed_at, "duration_sec": duration},
        )

    async def mark_failed(self, order_id: str, error_msg: str, retry_count: int) -> bool:
        return await self.update_one(
            {"order_id": order_id},
            {"status": "failed", "error_msg": error_msg, "retry_count": retry_count},
        )

    async def count_today(self, zone_id: Optional[str] = None) -> Dict:
        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        query = {"dispatched_at": {"$gte": today}}
        if zone_id:
            query["zone_id"] = zone_id.upper()

        total = await self.count(query)
        success = await self.count({**query, "status": "success"})
        failed = await self.count({**query, "status": "failed"})

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "failure_rate": round(failed / total * 100, 2) if total else 0,
        }

    async def count_last_n_days(self, days: int = 7, zone_id: Optional[str] = None) -> List[Dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = {"dispatched_at": {"$gte": since}}
        if zone_id:
            query["zone_id"] = zone_id.upper()

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$dispatched_at"}},
                    "status": "$status",
                },
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id.date": 1}},
        ]
        return await self._col().aggregate(pipeline).to_list(None)

    async def get_pair_performance(self, zone_id: Optional[str] = None) -> List[Dict]:
        query = {}
        if zone_id:
            query["zone_id"] = zone_id.upper()

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {"start": "$start_point", "end": "$end_point"},
                "total": {"$sum": 1},
                "success": {"$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}},
                "avg_duration": {"$avg": "$duration_sec"},
            }},
            {"$sort": {"total": -1}},
        ]
        return await self._col().aggregate(pipeline).to_list(None)


dispatch_log_repository = DispatchLogRepository()
