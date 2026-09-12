"""Node repository — collection: nodes. Implements NodeRepositoryPort."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from infrastructure.persistence.base_repository import BaseRepository


class NodeRepository(BaseRepository):
    def __init__(self):
        super().__init__("nodes")

    async def get_all(self) -> List[Dict]:
        return await self.find_many(
            {},
            sort=[("zone_id", 1), ("node_type", 1), ("priority", 1)],
        )

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

    async def set_maintenance(
        self, node_id: str, under: bool, reason: Optional[str]
    ) -> bool:
        data: Dict[str, Any] = {
            "is_under_maintenance": under,
            "maintenance_reason": (reason or "") if under else "",
        }
        return await self.update_one({"node_id": node_id}, data)

    async def set_lock(
        self,
        node_id: str,
        *,
        user: Optional[bool] = None,
        system: Optional[bool] = None,
        order_id: Optional[str] = None,
    ) -> bool:
        """
        Ghi một field `lock` = { user, system, orderId }.
        Chỉ cập nhật key được truyền (None = giữ nguyên).
        """
        doc = await self.get_by_id(node_id)
        if not doc:
            return False
        prev = doc.get("lock") if isinstance(doc.get("lock"), dict) else {}
        lock: Dict[str, Any] = {
            "user": bool(prev.get("user", False)),
            "system": bool(prev.get("system", False)),
            "orderId": prev.get("orderId"),
        }
        if user is not None:
            lock["user"] = bool(user)
        if system is not None:
            lock["system"] = bool(system)
            if not system:
                lock["orderId"] = None
            elif order_id is not None:
                lock["orderId"] = order_id
        elif order_id is not None and lock["system"]:
            lock["orderId"] = order_id
        return await self.update_one({"node_id": node_id}, {"lock": lock})

    async def clear_system_lock_by_order(self, order_id: str) -> List[str]:
        """Xóa lock.system trên mọi node có orderId khớp. Trả node_id đã sửa."""
        if not order_id:
            return []
        docs = await self.find_many(
            {"lock.system": True, "lock.orderId": order_id}
        )
        cleared: List[str] = []
        for doc in docs:
            nid = doc.get("node_id")
            if not nid:
                continue
            ok = await self.set_lock(nid, system=False)
            if ok:
                cleared.append(nid)
        return cleared

    async def list_with_lock(self) -> List[Dict]:
        """Node có user hoặc system lock (hydrate runtime sau restart)."""
        return await self.find_many(
            {
                "$or": [
                    {"lock.user": True},
                    {"lock.system": True},
                ]
            }
        )

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
