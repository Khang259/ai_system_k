"""Node use cases cho /api/v1 — list + maintenance + lock."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.fe_api.mappers import node_label
from application.ports import NodeRepositoryPort, NodeStateStore
from application.result import UseCaseResult


def _lock_from_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    raw = doc.get("lock") if isinstance(doc.get("lock"), dict) else {}
    return {
        "user": bool(raw.get("user", False)),
        "system": bool(raw.get("system", False)),
        "orderId": raw.get("orderId"),
    }


class GetNodes:
    def __init__(self, repo: NodeRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, zone_id: Optional[str] = None) -> UseCaseResult:
        if zone_id:
            docs = await self._repo.get_by_zone(zone_id)
        else:
            docs = await self._repo.get_all()

        items: List[Dict[str, Any]] = []
        for doc in docs:
            ntype = doc.get("node_type") or ""
            priority = doc.get("priority", 0)
            under = bool(doc.get("is_under_maintenance", False))
            items.append(
                {
                    "id": doc.get("node_id"),
                    "nodeId": doc.get("node_id"),
                    "label": node_label(ntype, priority),
                    "kind": ntype,
                    "zoneId": doc.get("zone_id"),
                    "cameraId": doc.get("camera_id"),
                    "priority": priority,
                    "enabled": bool(doc.get("enabled", True)),
                    "position": doc.get("position"),
                    "isUnderMaintenance": under,
                    "maintenanceReason": doc.get("maintenance_reason") or None,
                    # Một field `lock`: user (operator) + system (sau ICS)
                    "lock": _lock_from_doc(doc),
                }
            )
        return UseCaseResult.ok(items=items)


class SetMaintenance:
    """
    Bảo trì ≠ enabled; độc lập với `lock`.

    - `enabled=false`: node tắt hẳn khỏi cấu hình vận hành
    - `isUnderMaintenance`: tạm dừng dispatch, vẫn hiện trên UI với lý do
    """

    def __init__(self, repo: NodeRepositoryPort, state: NodeStateStore) -> None:
        self._repo = repo
        self._state = state

    async def execute(
        self,
        node_id: str,
        is_under_maintenance: bool,
        reason: Optional[str] = None,
    ) -> UseCaseResult:
        node = await self._repo.get_by_id(node_id)
        if not node:
            return UseCaseResult.fail(f"Node {node_id} not found", http_status=404)
        if is_under_maintenance and not (reason or "").strip():
            return UseCaseResult.fail(
                "Cần maintenanceReason khi bật bảo trì", http_status=400
            )
        await self._repo.set_maintenance(
            node_id, is_under_maintenance, (reason or "").strip() or None
        )
        if is_under_maintenance and self._state.is_ready():
            self._state.discard_from_ready(node_id)
        return UseCaseResult.ok(
            nodeId=node_id,
            isUnderMaintenance=is_under_maintenance,
            maintenanceReason=(reason or "").strip() or None,
        )


class SetLock:
    """Operator bật user-lock (Mongo `lock.user` + RAM). Không đụng system."""

    def __init__(self, repo: NodeRepositoryPort, state: NodeStateStore) -> None:
        self._repo = repo
        self._state = state

    async def execute(self, node_id: str, user: bool = True) -> UseCaseResult:
        node = await self._repo.get_by_id(node_id)
        if not node:
            return UseCaseResult.fail(f"Node {node_id} not found", http_status=404)
        if not user:
            return UseCaseResult.fail(
                "Dùng /unlock để tắt lock (user/system)", http_status=400
            )
        await self._repo.set_lock(node_id, user=True)
        fresh = await self._repo.get_by_id(node_id) or {}
        lock = _lock_from_doc(fresh)
        if self._state.is_ready() and hasattr(self._state, "apply_persisted_lock"):
            self._state.apply_persisted_lock(
                node_id,
                user=lock["user"],
                system=lock["system"],
                order_id=lock.get("orderId"),
            )
        return UseCaseResult.ok(nodeId=node_id, lock=lock)


class Unlock:
    """Gỡ user và/hoặc system lock trên một node."""

    def __init__(self, repo: NodeRepositoryPort, state: NodeStateStore) -> None:
        self._repo = repo
        self._state = state

    async def execute(
        self, node_id: str, *, user: bool = False, system: bool = False
    ) -> UseCaseResult:
        if not user and not system:
            return UseCaseResult.fail(
                "Cần user=true và/hoặc system=true", http_status=400
            )
        node = await self._repo.get_by_id(node_id)
        if not node:
            return UseCaseResult.fail(f"Node {node_id} not found", http_status=404)

        kwargs: Dict[str, Any] = {}
        if user:
            kwargs["user"] = False
        if system:
            kwargs["system"] = False
        await self._repo.set_lock(node_id, **kwargs)

        fresh = await self._repo.get_by_id(node_id) or {}
        lock = _lock_from_doc(fresh)
        if self._state.is_ready() and hasattr(self._state, "apply_persisted_lock"):
            self._state.apply_persisted_lock(
                node_id,
                user=lock["user"],
                system=lock["system"],
                order_id=lock.get("orderId"),
            )
        return UseCaseResult.ok(nodeId=node_id, lock=lock)
