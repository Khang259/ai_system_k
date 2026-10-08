"""Create / Delete camera (+ observedNodeIds SSOT)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.fe_api.cameras_helpers import (
    _kind_from_node_id,
    _normalize_observed_ids,
    _priority_for_new_node,
    _reject_duplicate_rtsp,
)
from application.fe_api.mappers import node_label
from application.fe_api.priority_rules import ensure_start_priority_unique
from application.fe_api.sync_rules import (
    cascade_delete_node,
    cascade_delete_pairs_for_node,
    require_inference_paused,
)
from application.ports import (
    CameraConfigRepository,
    CameraRuntime,
    InferencePort,
    NodeRepositoryPort,
    NodeStateStore,
    PairsRepositoryPort,
)
from application.result import UseCaseResult


class CreateCamera:
    """
    Tạo camera mới — auto cameraId = max(existing)+1.

    observedNodeIds cần zone (create/gán node).
    Node thuộc camera khác → 409.
    """

    def __init__(
        self,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        runtime: CameraRuntime,
        inference: InferencePort,
        resolution: str,
    ) -> None:
        self._cameras = cameras
        self._nodes = nodes
        self._runtime = runtime
        self._inference = inference
        self._resolution = resolution

    async def execute(
        self,
        *,
        name: str,
        rtsp_url: str,
        zone: Optional[str] = None,
        observed_node_ids: Optional[List[str]] = None,
        node_priorities: Optional[Dict[str, int]] = None,
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate

        name_s = str(name or "").strip()
        if not name_s:
            return UseCaseResult.fail("name không được rỗng", http_status=400)
        url_s = str(rtsp_url or "").strip()
        if not url_s:
            return UseCaseResult.fail("rtspUrl không được rỗng", http_status=400)

        zone_s = ""
        if zone is not None:
            zone_s = str(zone).strip().upper()
            if not zone_s:
                return UseCaseResult.fail("zone không được rỗng", http_status=400)

        desired_ids, fail = _normalize_observed_ids(observed_node_ids)
        if fail:
            return fail
        if desired_ids and not zone_s:
            return UseCaseResult.fail(
                "Cần zone khi gán observedNodeIds",
                http_status=400,
            )

        existing = await self._cameras.get_all()
        dup = await _reject_duplicate_rtsp(
            self._cameras, url_s, existing=existing
        )
        if dup:
            return dup
        next_id = (
            max((int(d.get("cameraId") or 0) for d in existing), default=0) + 1
        )

        to_create: List[str] = []
        to_assign: List[str] = []
        if desired_ids:
            for nid in desired_ids:
                existing_node = await self._nodes.get_by_id(nid)
                if existing_node is None:
                    to_create.append(nid)
                    continue
                other = existing_node.get("camera_id")
                if other is not None and int(other) != int(next_id):
                    return UseCaseResult.fail(
                        f"Node {nid} đang thuộc camera {other} "
                        "(1 node chỉ gắn 1 camera)",
                        http_status=409,
                    )
                to_assign.append(nid)

        # Validate priority trước khi ghi camera (tránh orphan cam nếu fail)
        create_priorities: Dict[str, int] = {}
        reserved: Dict[int, str] = {}
        for nid in to_create:
            ntype = _kind_from_node_id(nid)
            assert ntype is not None
            p, err = await _priority_for_new_node(
                self._nodes, nid, ntype, zone_s, node_priorities, reserved=reserved
            )
            if err:
                return err
            assert p is not None
            create_priorities[nid] = p

        doc: Dict[str, Any] = {
            "cameraId": next_id,
            "name": name_s,
            "url": url_s,
            "zone_id": zone_s,
            "enabled": True,
            "rois": {},
        }
        await self._cameras.create(doc)

        observed_created = 0
        for nid in to_create:
            ntype = _kind_from_node_id(nid)
            assert ntype is not None
            await self._nodes.create(
                {
                    "node_id": nid,
                    "node_type": ntype,
                    "zone_id": zone_s,
                    "camera_id": int(next_id),
                    "priority": create_priorities[nid],
                    "enabled": True,
                    "is_under_maintenance": False,
                    "maintenance_reason": "",
                    "lock": {
                        "user": False,
                        "system": False,
                        "orderId": None,
                    },
                }
            )
            observed_created += 1

        for nid in to_assign:
            await self._nodes.update_by_node_id(
                nid,
                {
                    "camera_id": int(next_id),
                    "zone_id": zone_s,
                },
            )

        observed_assigned = observed_created + len(to_assign)

        nodes = await self._nodes.get_by_camera(next_id)
        return UseCaseResult.ok(
            cameraId=next_id,
            name=name_s,
            rtspUrl=url_s,
            zone=zone_s,
            status="offline",
            resolution=self._resolution,
            mapPosition=None,
            observedNodeIds=[n.get("node_id") for n in nodes if n.get("node_id")],
            enabled=True,
            error=None,
            requiresRestart=bool(self._runtime.is_ready()),
            observedAssigned=observed_assigned,
            observedCreated=observed_created,
        )



class DeleteCamera:
    """Xóa camera + cascade mọi node thuộc camera (kèm pair + ROI)."""

    def __init__(
        self,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        pairs: PairsRepositoryPort,
        inference: InferencePort,
        state: NodeStateStore,
    ) -> None:
        self._cameras = cameras
        self._nodes = nodes
        self._pairs = pairs
        self._inference = inference
        self._state = state

    async def execute(self, camera_id: int) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate
        doc = await self._cameras.get_by_id(camera_id)
        if not doc:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)

        owned = await self._nodes.get_by_camera(camera_id)
        nodes_deleted: List[str] = []
        pairs_deleted: List[str] = []
        for n in owned:
            nid = n.get("node_id")
            if not nid:
                continue
            stats = await cascade_delete_node(
                nodes=self._nodes,
                cameras=self._cameras,
                pairs=self._pairs,
                state=self._state,
                node_id=str(nid),
            )
            if stats["deleted"]:
                nodes_deleted.append(str(nid))
                pairs_deleted.extend(stats["pairsDeleted"])

        ok = await self._cameras.delete_by_camera_id(camera_id)
        if not ok:
            return UseCaseResult.fail(
                f"Không xóa được camera {camera_id}", http_status=500
            )
        return UseCaseResult.ok(
            cameraId=camera_id,
            deleted=True,
            nodesDeleted=nodes_deleted,
            pairsDeleted=pairs_deleted,
        )

