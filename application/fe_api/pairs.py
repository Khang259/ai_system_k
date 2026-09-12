"""Node pairs use cases cho /api/v1."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.ports import NodeRepositoryPort, PairsRepositoryPort
from application.result import UseCaseResult


class GetNodePairs:
    def __init__(
        self,
        pairs: PairsRepositoryPort,
        nodes: NodeRepositoryPort,
    ) -> None:
        self._pairs = pairs
        self._nodes = nodes

    async def execute(self, zone_id: Optional[str] = None) -> UseCaseResult:
        if zone_id:
            docs = await self._pairs.get_by_zone(zone_id)
        else:
            docs = await self._pairs.list_all()

        node_cache: Dict[str, Dict[str, Any]] = {}

        async def _node(nid: Optional[str]) -> Optional[Dict[str, Any]]:
            if not nid:
                return None
            if nid not in node_cache:
                node_cache[nid] = await self._nodes.get_by_id(nid) or {}
            return node_cache[nid]

        items: List[Dict[str, Any]] = []
        for doc in docs:
            start = doc.get("start_point") or ""
            end = doc.get("end_point")
            pair_id = f"{start}:{end or '_'}"
            name = doc.get("name") or (
                f"{start} → {end}" if end else f"{start} (empty)"
            )

            blocked = False
            reasons: List[str] = []
            if not doc.get("enabled", True):
                blocked = True
                reasons.append("Pair disabled")

            for nid, role in ((start, "start"), (end, "end")):
                if not nid:
                    continue
                node = await _node(nid)
                if not node:
                    blocked = True
                    reasons.append(f"{role} node missing")
                    continue
                if not node.get("enabled", True):
                    blocked = True
                    reasons.append(f"{role} node disabled")
                if node.get("is_under_maintenance"):
                    blocked = True
                    reason = node.get("maintenance_reason") or "under maintenance"
                    reasons.append(f"{role} node: {reason}")

            items.append(
                {
                    "id": pair_id,
                    "name": name,
                    "zoneId": doc.get("zone_id"),
                    "startNodeId": start,
                    "endNodeId": end,
                    "pairType": doc.get("pair_type"),
                    "enabled": bool(doc.get("enabled", True)),
                    "autoDispatch": bool(doc.get("auto_dispatch", True)),
                    "isBlocked": blocked,
                    "blockedReason": "; ".join(reasons) if reasons else None,
                }
            )
        return UseCaseResult.ok(items=items)
