"""Update camera (+ observedNodeIds SSOT)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.fe_api.cameras_helpers import (
    _kind_from_node_id,
    _normalize_observed_ids,
    _priority_for_new_node,
    _reject_duplicate_rtsp,
)
from application.fe_api.mappers import camera_status, node_label
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


class UpdateCamera:
    """
    Partial update name / RTSP / zone / observedNodeIds.

    Cây SSOT: cameras → nodes → pairs.
    Gỡ node khỏi observedNodeIds → cascade xóa pair + ROI + node.
    Node đã thuộc camera khác → 409.
    """

    def __init__(
        self,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        pairs: PairsRepositoryPort,
        runtime: CameraRuntime,
        inference: InferencePort,
        state: NodeStateStore,
        resolution: str,
    ) -> None:
        self._cameras = cameras
        self._nodes = nodes
        self._pairs = pairs
        self._runtime = runtime
        self._inference = inference
        self._state = state
        self._resolution = resolution

    async def execute(
        self,
        camera_id: int,
        *,
        name: Optional[str] = None,
        rtsp_url: Optional[str] = None,
        zone: Optional[str] = None,
        observed_node_ids: Optional[List[str]] = None,
        node_priorities: Optional[Dict[str, int]] = None,
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate

        if (
            name is None
            and rtsp_url is None
            and zone is None
            and observed_node_ids is None
        ):
            return UseCaseResult.fail(
                "Cần ít nhất một field: name, rtspUrl, zone, observedNodeIds",
                http_status=400,
            )

        doc = await self._cameras.get_by_id(camera_id)
        if not doc:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)

        patch: Dict[str, Any] = {}
        if name is not None:
            name_s = str(name).strip()
            if not name_s:
                return UseCaseResult.fail("name không được rỗng", http_status=400)
            patch["name"] = name_s
        if rtsp_url is not None:
            url_s = str(rtsp_url).strip()
            if not url_s:
                return UseCaseResult.fail("rtspUrl không được rỗng", http_status=400)
            patch["url"] = url_s
        if zone is not None:
            zone_s = str(zone).strip().upper()
            if not zone_s:
                return UseCaseResult.fail("zone không được rỗng", http_status=400)
            patch["zone_id"] = zone_s

        desired_ids, obs_fail = _normalize_observed_ids(observed_node_ids)
        if obs_fail:
            return obs_fail

        old_url = (doc.get("url") or "").strip()
        url_changed = "url" in patch and patch["url"] != old_url
        if url_changed:
            dup = await _reject_duplicate_rtsp(
                self._cameras,
                patch["url"],
                exclude_camera_id=camera_id,
            )
            if dup:
                return dup

        if "zone_id" in patch:
            new_zone = patch["zone_id"]
            cam_nodes = await self._nodes.get_by_camera(camera_id)
            for n in cam_nodes:
                if (n.get("node_type") or "").lower() != "start":
                    continue
                nid = n.get("node_id")
                if not nid:
                    continue
                try:
                    p = int(n.get("priority"))
                except (TypeError, ValueError):
                    continue
                conflict = await ensure_start_priority_unique(
                    self._nodes,
                    new_zone,
                    p,
                    exclude_node_id=str(nid),
                )
                if conflict:
                    return conflict

        if patch:
            await self._cameras.update_by_camera_id(camera_id, patch)

        nodes_updated = 0
        if "zone_id" in patch:
            nodes_updated = await self._nodes.set_zone_by_camera(
                camera_id, patch["zone_id"]
            )

        observed_assigned = 0
        observed_removed = 0
        observed_created = 0
        pairs_deleted: List[str] = []
        if desired_ids is not None:
            fresh_zone = str(
                patch.get("zone_id") or (doc.get("zone_id") or "")
            ).strip().upper()
            if not fresh_zone:
                return UseCaseResult.fail(
                    "Camera chưa có zone — không tạo/gán được node",
                    http_status=400,
                )

            current = await self._nodes.get_by_camera(camera_id)
            current_ids = {
                str(n.get("node_id"))
                for n in current
                if n.get("node_id")
            }
            desired_set = set(desired_ids)

            create_priorities: Dict[str, int] = {}
            reserved: Dict[int, str] = {}
            for nid in desired_ids:
                existing = await self._nodes.get_by_id(nid)
                if existing is None:
                    ntype = _kind_from_node_id(nid)
                    assert ntype is not None
                    p, err = await _priority_for_new_node(
                        self._nodes,
                        nid,
                        ntype,
                        fresh_zone,
                        node_priorities,
                        reserved=reserved,
                    )
                    if err:
                        return err
                    assert p is not None
                    create_priorities[nid] = p
                else:
                    other = existing.get("camera_id")
                    if other is not None and int(other) != int(camera_id):
                        return UseCaseResult.fail(
                            f"Node {nid} đang thuộc camera {other} "
                            "(1 node chỉ gắn 1 camera)",
                            http_status=409,
                        )

            for nid in desired_ids:
                existing = await self._nodes.get_by_id(nid)
                if existing is None:
                    ntype = _kind_from_node_id(nid)
                    assert ntype is not None
                    await self._nodes.create(
                        {
                            "node_id": nid,
                            "node_type": ntype,
                            "zone_id": fresh_zone,
                            "camera_id": int(camera_id),
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
                else:
                    await self._nodes.update_by_node_id(
                        nid,
                        {
                            "camera_id": int(camera_id),
                            "zone_id": fresh_zone,
                        },
                    )
                observed_assigned += 1

            for nid in current_ids - desired_set:
                stats = await cascade_delete_node(
                    nodes=self._nodes,
                    cameras=self._cameras,
                    pairs=self._pairs,
                    state=self._state,
                    node_id=nid,
                )
                if stats["deleted"]:
                    observed_removed += 1
                    pairs_deleted.extend(stats["pairsDeleted"])
        fresh = await self._cameras.get_by_id(camera_id) or {**doc, **patch}
        nodes = await self._nodes.get_by_camera(camera_id)
        runtime_row = None
        if self._runtime.is_ready():
            for row in self._runtime.get_status().get("cameras") or []:
                if row.get("cameraId") == camera_id:
                    runtime_row = row
                    break

        item = {
            "cameraId": camera_id,
            "name": fresh.get("name") or f"Camera {camera_id}",
            "rtspUrl": fresh.get("url") or "",
            "zone": fresh.get("zone_id") or "",
            "status": camera_status(bool(fresh.get("enabled", True)), runtime_row),
            "resolution": self._resolution,
            "mapPosition": fresh.get("mapPosition") or fresh.get("map_position"),
            "observedNodeIds": [n.get("node_id") for n in nodes if n.get("node_id")],
            "enabled": bool(fresh.get("enabled", True)),
            "error": (runtime_row or {}).get("error"),
            "requiresRestart": bool(url_changed and self._runtime.is_ready()),
            "nodesZoneUpdated": nodes_updated,
            "observedAssigned": observed_assigned,
            "observedRemoved": observed_removed,
            "observedCreated": observed_created,
            "pairsDeleted": pairs_deleted,
            "observedUnassigned": observed_removed,
        }
        return UseCaseResult.ok(**item)


