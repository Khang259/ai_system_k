"""Node pairs use cases cho /api/v1."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from application.fe_api.sync_rules import (
    require_inference_paused,
    require_node_ready_for_pair,
)
from application.ports import (
    CameraConfigRepository,
    InferencePort,
    NodeRepositoryPort,
    PairsRepositoryPort,
    RuntimeControl,
)
from application.result import UseCaseResult


def parse_pair_id(pair_id: str) -> Tuple[str, Optional[str]]:
    """`start:end` hoặc `start:_` (empty pair)."""
    if not pair_id or ":" not in pair_id:
        raise ValueError("Invalid pair id")
    start, end = pair_id.split(":", 1)
    if not start.strip():
        raise ValueError("Invalid pair id")
    if end == "_":
        return start, None
    return start, end or None


def make_pair_id(start: str, end: Optional[str]) -> str:
    return f"{start}:{end or '_'}"


async def _resolve_key(
    pair_id: Optional[str],
    start_node_id: Optional[str],
    end_node_id: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[UseCaseResult]]:
    if pair_id:
        try:
            start, end = parse_pair_id(pair_id)
            return start, end, None
        except ValueError:
            return None, None, UseCaseResult.fail("id pair không hợp lệ", http_status=400)
    if start_node_id:
        return start_node_id, end_node_id, None
    return None, None, UseCaseResult.fail(
        "Cần id hoặc startNodeId", http_status=400
    )


async def _validate_nodes_for_pair(
    nodes: NodeRepositoryPort,
    cameras: CameraConfigRepository,
    start_id: str,
    end_id: Optional[str],
    pair_type: str,
) -> Optional[UseCaseResult]:
    if pair_type not in ("normal", "empty"):
        return UseCaseResult.fail("pairType phải là normal hoặc empty", http_status=400)
    err = await require_node_ready_for_pair(nodes, cameras, start_id, "Start")
    if err:
        return err
    if pair_type == "normal":
        if not end_id:
            return UseCaseResult.fail(
                "endNodeId bắt buộc với pairType=normal", http_status=400
            )
        return await require_node_ready_for_pair(nodes, cameras, end_id, "End")
    return None


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
            pair_id = make_pair_id(start, end)
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
                lock = node.get("lock") if isinstance(node.get("lock"), dict) else {}
                if lock.get("user") or lock.get("system"):
                    blocked = True
                    reasons.append(f"{role} node locked")

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


class CreatePairFe:
    def __init__(
        self,
        pairs: PairsRepositoryPort,
        nodes: NodeRepositoryPort,
        cameras: CameraConfigRepository,
        runtime: RuntimeControl,
        inference: InferencePort,
    ) -> None:
        self._pairs = pairs
        self._nodes = nodes
        self._cameras = cameras
        self._runtime = runtime
        self._inference = inference

    async def execute(
        self,
        start_node_id: str,
        zone_id: str,
        pair_type: str = "normal",
        end_node_id: Optional[str] = None,
        enabled: bool = True,
        auto_dispatch: bool = True,
        name: Optional[str] = None,
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate

        pair_type = (pair_type or "normal").lower().strip()
        zone = (zone_id or "").upper().strip()
        if not zone:
            return UseCaseResult.fail("zoneId không được rỗng", http_status=400)

        err = await _validate_nodes_for_pair(
            self._nodes, self._cameras, start_node_id, end_node_id, pair_type
        )
        if err:
            return err

        end_key = None if pair_type == "empty" else end_node_id
        if await self._pairs.find_by_key(start_node_id, end_key):
            return UseCaseResult.fail("Pair đã tồn tại", http_status=409)

        doc: Dict[str, Any] = {
            "start_point": start_node_id,
            "end_point": end_key,
            "zone_id": zone,
            "pair_type": pair_type,
            "enabled": enabled,
            "auto_dispatch": auto_dispatch,
        }
        if name and name.strip():
            doc["name"] = name.strip()

        await self._pairs.create(doc)
        await self._runtime.reload()
        return UseCaseResult.ok(
            id=make_pair_id(start_node_id, end_key),
            startNodeId=start_node_id,
            endNodeId=end_key,
            zoneId=zone,
            pairType=pair_type,
            enabled=enabled,
            autoDispatch=auto_dispatch,
            runtimeReloaded=True,
        )


class UpdatePairFe:
    def __init__(
        self,
        pairs: PairsRepositoryPort,
        nodes: NodeRepositoryPort,
        cameras: CameraConfigRepository,
        runtime: RuntimeControl,
        inference: InferencePort,
    ) -> None:
        self._pairs = pairs
        self._nodes = nodes
        self._cameras = cameras
        self._runtime = runtime
        self._inference = inference

    async def execute(
        self,
        pair_id: str,
        start_node_id: Optional[str] = None,
        end_node_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        pair_type: Optional[str] = None,
        enabled: Optional[bool] = None,
        auto_dispatch: Optional[bool] = None,
        name: Optional[str] = None,
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate

        try:
            old_start, old_end = parse_pair_id(pair_id)
        except ValueError:
            return UseCaseResult.fail("id pair không hợp lệ", http_status=400)

        current = await self._pairs.find_by_key(old_start, old_end)
        if not current:
            return UseCaseResult.fail("Pair không tồn tại", http_status=404)

        if not any(
            v is not None
            for v in (
                start_node_id,
                end_node_id,
                zone_id,
                pair_type,
                enabled,
                auto_dispatch,
                name,
            )
        ):
            return UseCaseResult.fail("Cần ít nhất một field để sửa", http_status=400)

        new_type = (
            (pair_type or current.get("pair_type") or "normal").lower().strip()
        )
        new_start = start_node_id or old_start
        new_end = end_node_id if end_node_id is not None else old_end
        if pair_type == "empty":
            new_end = None
        elif new_type == "empty":
            new_end = None

        identity_changed = (
            start_node_id is not None
            or end_node_id is not None
            or pair_type is not None
        )
        if identity_changed:
            err = await _validate_nodes_for_pair(
                self._nodes, self._cameras, new_start, new_end, new_type
            )
            if err:
                return err

        if (new_start, new_end) != (old_start, old_end):
            dup = await self._pairs.find_by_key(new_start, new_end)
            if dup:
                return UseCaseResult.fail("Pair đích đã tồn tại", http_status=409)

        updates: Dict[str, Any] = {
            "start_point": new_start,
            "end_point": new_end,
            "pair_type": new_type,
        }
        if zone_id is not None:
            zone = zone_id.upper().strip()
            if not zone:
                return UseCaseResult.fail("zoneId không được rỗng", http_status=400)
            updates["zone_id"] = zone
        if enabled is not None:
            updates["enabled"] = enabled
        if auto_dispatch is not None:
            updates["auto_dispatch"] = auto_dispatch
        if name is not None:
            updates["name"] = name.strip() or None

        ok = await self._pairs.update_by_key(old_start, old_end, updates)
        if not ok:
            return UseCaseResult.fail("Pair không tồn tại", http_status=404)

        await self._runtime.reload()
        final_zone = updates.get("zone_id", current.get("zone_id"))
        return UseCaseResult.ok(
            id=make_pair_id(new_start, new_end),
            startNodeId=new_start,
            endNodeId=new_end,
            zoneId=final_zone,
            pairType=new_type,
            enabled=updates.get("enabled", current.get("enabled", True)),
            autoDispatch=updates.get(
                "auto_dispatch", current.get("auto_dispatch", True)
            ),
            runtimeReloaded=True,
        )


class DeletePairFe:
    def __init__(
        self,
        pairs: PairsRepositoryPort,
        runtime: RuntimeControl,
        inference: InferencePort,
    ) -> None:
        self._pairs = pairs
        self._runtime = runtime
        self._inference = inference

    async def execute(
        self,
        pair_id: Optional[str] = None,
        start_node_id: Optional[str] = None,
        end_node_id: Optional[str] = None,
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate

        start, end, err = await _resolve_key(pair_id, start_node_id, end_node_id)
        if err:
            return err

        ok = await self._pairs.delete(start, end)
        if not ok:
            return UseCaseResult.fail("Pair không tồn tại", http_status=404)

        await self._runtime.reload()
        return UseCaseResult.ok(
            id=make_pair_id(start, end),
            startNodeId=start,
            endNodeId=end,
            runtimeReloaded=True,
        )


class SetPairEnabledFe:
    def __init__(
        self,
        pairs: PairsRepositoryPort,
        runtime: RuntimeControl,
        inference: InferencePort,
    ) -> None:
        self._pairs = pairs
        self._runtime = runtime
        self._inference = inference

    async def execute(
        self,
        enabled: bool,
        pair_id: Optional[str] = None,
        start_node_id: Optional[str] = None,
        end_node_id: Optional[str] = None,
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate

        start, end, err = await _resolve_key(pair_id, start_node_id, end_node_id)
        if err:
            return err

        ok = await self._pairs.set_enabled(start, end, enabled)
        if not ok:
            return UseCaseResult.fail("Pair không tồn tại", http_status=404)

        await self._runtime.reload()
        return UseCaseResult.ok(
            id=make_pair_id(start, end),
            startNodeId=start,
            endNodeId=end,
            enabled=enabled,
            runtimeReloaded=True,
        )
