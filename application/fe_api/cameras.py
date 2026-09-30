"""Camera + ROI use cases cho /api/v1."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.fe_api.mappers import (
    camera_status,
    node_label,
    parse_roi_id,
    roi_item,
    validate_box,
)
from application.fe_api.sync_rules import (
    cascade_delete_node,
    cascade_delete_pairs_for_node,
    require_inference_paused,
    set_pairs_enabled_for_nodes,
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


class GetCameras:
    def __init__(
        self,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        runtime: CameraRuntime,
        resolution: str,
    ) -> None:
        self._cameras = cameras
        self._nodes = nodes
        self._runtime = runtime
        self._resolution = resolution

    async def execute(self) -> UseCaseResult:
        docs = await self._cameras.get_all()
        runtime_by_id: Dict[int, Dict[str, Any]] = {}
        if self._runtime.is_ready():
            for row in self._runtime.get_status().get("cameras") or []:
                cid = row.get("cameraId")
                if cid is not None:
                    runtime_by_id[int(cid)] = row

        items: List[Dict[str, Any]] = []
        for doc in docs:
            cid = int(doc.get("cameraId"))
            nodes = await self._nodes.get_by_camera(cid)
            db_enabled = bool(doc.get("enabled", True))
            items.append(
                {
                    "cameraId": cid,
                    "name": doc.get("name") or f"Camera {cid}",
                    "rtspUrl": doc.get("url") or "",
                    "zone": doc.get("zone_id") or "",
                    "status": camera_status(db_enabled, runtime_by_id.get(cid)),
                    "resolution": self._resolution,
                    "mapPosition": doc.get("mapPosition") or doc.get("map_position"),
                    "observedNodeIds": [n.get("node_id") for n in nodes if n.get("node_id")],
                    "enabled": db_enabled,
                    "error": (runtime_by_id.get(cid) or {}).get("error"),
                }
            )
        return UseCaseResult.ok(items=items)


class GetRois:
    def __init__(
        self,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        ref_width: int,
        ref_height: int,
    ) -> None:
        self._cameras = cameras
        self._nodes = nodes
        self._ref_w = ref_width
        self._ref_h = ref_height

    async def execute(self, camera_id: Optional[int] = None) -> UseCaseResult:
        if camera_id is not None:
            doc = await self._cameras.get_by_id(camera_id)
            docs = [doc] if doc else []
        else:
            docs = await self._cameras.get_all()

        items: List[Dict[str, Any]] = []
        for doc in docs:
            if not doc:
                continue
            cid = int(doc["cameraId"])
            rois = doc.get("rois") or {}
            if not isinstance(rois, dict):
                continue
            for node_id, entry in rois.items():
                node = await self._nodes.get_by_id(node_id)
                ntype = (node or {}).get("node_type") or (
                    "start" if str(node_id).startswith("start_") else "end"
                )
                priority = (node or {}).get("priority", 0)
                items.append(
                    roi_item(
                        cid,
                        node_id,
                        entry,
                        label=node_label(ntype, priority),
                        kind=ntype,
                        ref_width=self._ref_w,
                        ref_height=self._ref_h,
                    )
                )
        return UseCaseResult.ok(items=items)


class SetCameraStatus:
    """
    Bật/tắt camera + cascade nodes + pairs cùng camera.
    Cần inference paused khi runtime đang chạy.
    """

    def __init__(
        self,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        pairs: PairsRepositoryPort,
        runtime: CameraRuntime,
        inference: InferencePort,
        state: NodeStateStore,
    ) -> None:
        self._cameras = cameras
        self._nodes = nodes
        self._pairs = pairs
        self._runtime = runtime
        self._inference = inference
        self._state = state

    async def execute(self, camera_id: int, enabled: bool) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate
        doc = await self._cameras.get_by_id(camera_id)
        if not doc:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)

        await self._cameras.set_enabled(camera_id, enabled)
        if self._runtime.is_ready():
            self._runtime.set_camera_enabled_by_id(camera_id, enabled)

        owned = await self._nodes.get_by_camera(camera_id)
        node_ids = {str(n.get("node_id")) for n in owned if n.get("node_id")}
        nodes_updated = 0
        for nid in node_ids:
            if await self._nodes.set_enabled(nid, enabled):
                nodes_updated += 1
            if not enabled and self._state.is_ready():
                self._state.discard_from_ready(nid)

        pairs_updated = await set_pairs_enabled_for_nodes(
            self._pairs, node_ids, enabled
        )
        return UseCaseResult.ok(
            cameraId=camera_id,
            enabled=enabled,
            nodesUpdated=nodes_updated,
            pairsUpdated=pairs_updated,
        )


def _kind_from_node_id(node_id: str) -> Optional[str]:
    if node_id.startswith("start_"):
        return "start"
    if node_id.startswith("end_"):
        return "end"
    return None


def _normalize_observed_ids(
    observed_node_ids: Optional[List[str]],
) -> tuple[Optional[List[str]], Optional[UseCaseResult]]:
    if observed_node_ids is None:
        return None, None
    seen = set()
    desired: List[str] = []
    for raw in observed_node_ids:
        nid = str(raw or "").strip()
        if not nid or nid in seen:
            continue
        seen.add(nid)
        desired.append(nid)
    for nid in desired:
        if _kind_from_node_id(nid) is None:
            return None, UseCaseResult.fail(
                f"nodeId '{nid}' phải bắt đầu bằng start_ hoặc end_",
                http_status=400,
            )
    return desired, None


async def _reject_duplicate_rtsp(
    cameras: CameraConfigRepository,
    rtsp_url: str,
    *,
    exclude_camera_id: Optional[int] = None,
    existing: Optional[List[Dict[str, Any]]] = None,
) -> Optional[UseCaseResult]:
    """rtspUrl phải unique giữa cameras → 409 nếu trùng."""
    url = rtsp_url.strip()
    docs = existing if existing is not None else await cameras.get_all()
    for doc in docs:
        cid = doc.get("cameraId")
        if cid is None:
            continue
        if exclude_camera_id is not None and int(cid) == int(exclude_camera_id):
            continue
        if (doc.get("url") or "").strip() == url:
            return UseCaseResult.fail(
                f"rtspUrl đã dùng bởi camera {int(cid)}",
                http_status=409,
            )
    return None


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
                    "priority": 999,
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
                            "priority": 999,
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
                    other = existing.get("camera_id")
                    if other is not None and int(other) != int(camera_id):
                        return UseCaseResult.fail(
                            f"Node {nid} đang thuộc camera {other} "
                            "(1 node chỉ gắn 1 camera)",
                            http_status=409,
                        )
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


class _RoiWriteBase:
    def __init__(
        self,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        ref_width: int,
        ref_height: int,
        inference: InferencePort,
        pairs: Optional[PairsRepositoryPort] = None,
    ) -> None:
        self._cameras = cameras
        self._nodes = nodes
        self._ref_w = ref_width
        self._ref_h = ref_height
        self._inference = inference
        self._pairs = pairs

    async def _resolve(
        self,
        camera_id: Optional[int],
        node_id: Optional[str],
        roi_id: Optional[str],
    ):
        if roi_id:
            parsed = parse_roi_id(roi_id)
            if not parsed:
                return None, None, UseCaseResult.fail(
                    "id ROI phải dạng {cameraId}:{nodeId}", http_status=400
                )
            camera_id, node_id = parsed
        if camera_id is None or not node_id:
            return None, None, UseCaseResult.fail(
                "Cần cameraId + nodeId hoặc id", http_status=400
            )
        return int(camera_id), node_id, None

    def _roi_doc(self, box: List[Any], node_type: str) -> Dict[str, Any]:
        is_start = node_type == "start"
        return {
            "roi": [float(v) for v in box],
            "start": is_start,
            "end": not is_start,
            "ref_width": self._ref_w,
            "ref_height": self._ref_h,
        }


class CreateRoi(_RoiWriteBase):
    async def execute(
        self,
        camera_id: int,
        node_id: str,
        box: List[Any],
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate
        err = validate_box(box, self._ref_w, self._ref_h)
        if err:
            return UseCaseResult.fail(err, http_status=400)
        cam = await self._cameras.get_by_id(camera_id)
        if not cam:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)
        node = await self._nodes.get_by_id(node_id)
        if not node:
            return UseCaseResult.fail(f"Node {node_id} not found", http_status=404)
        other = node.get("camera_id")
        if other is None or int(other) != int(camera_id):
            return UseCaseResult.fail(
                f"Node {node_id} phải nằm trong observedNodeIds của camera {camera_id}",
                http_status=400,
            )
        ntype = node.get("node_type") or (
            "start" if node_id.startswith("start_") else "end"
        )
        ok = await self._cameras.upsert_roi(
            camera_id, node_id, self._roi_doc(box, ntype)
        )
        if not ok:
            cam2 = await self._cameras.get_by_id(camera_id)
            rois = (cam2 or {}).get("rois") or {}
            if node_id not in rois:
                return UseCaseResult.fail("Không ghi được ROI", http_status=500)
        item = roi_item(
            camera_id,
            node_id,
            self._roi_doc(box, ntype),
            label=node_label(ntype, node.get("priority", 0)),
            kind=ntype,
            ref_width=self._ref_w,
            ref_height=self._ref_h,
        )
        return UseCaseResult.ok(**item)


class UpdateRoi(_RoiWriteBase):
    """Cập nhật một hoặc nhiều ROI. Validate hết rồi mới ghi (fail-fast trước write)."""

    async def execute(self, items: List[Dict[str, Any]]) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate
        if not items:
            return UseCaseResult.fail("Cần ít nhất 1 ROI trong items", http_status=400)

        prepared: List[Dict[str, Any]] = []
        cam_cache: Dict[int, Dict[str, Any]] = {}

        for i, raw in enumerate(items):
            box = raw.get("box")
            err = validate_box(box or [], self._ref_w, self._ref_h)
            if err:
                return UseCaseResult.fail(f"items[{i}]: {err}", http_status=400)

            camera_id, node_id, fail = await self._resolve(
                raw.get("cameraId") if raw.get("cameraId") is not None else raw.get("camera_id"),
                raw.get("nodeId") or raw.get("node_id"),
                raw.get("id") or raw.get("roi_id"),
            )
            if fail:
                return UseCaseResult.fail(
                    f"items[{i}]: {fail.error}",
                    http_status=int(fail.data.get("http_status") or 400),
                )

            if camera_id not in cam_cache:
                cam = await self._cameras.get_by_id(camera_id)
                if not cam:
                    return UseCaseResult.fail(
                        f"items[{i}]: Camera {camera_id} not found",
                        http_status=404,
                    )
                cam_cache[camera_id] = cam
            rois = cam_cache[camera_id].get("rois") or {}
            if node_id not in rois:
                return UseCaseResult.fail(
                    f"items[{i}]: ROI không tồn tại ({camera_id}:{node_id})",
                    http_status=404,
                )

            node = await self._nodes.get_by_id(node_id)
            ntype = (node or {}).get("node_type") or (
                "start" if node_id.startswith("start_") else "end"
            )
            doc = self._roi_doc(list(box), ntype)
            prepared.append(
                {
                    "camera_id": camera_id,
                    "node_id": node_id,
                    "doc": doc,
                    "ntype": ntype,
                    "priority": (node or {}).get("priority", 0),
                }
            )

        out: List[Dict[str, Any]] = []
        for row in prepared:
            await self._cameras.upsert_roi(row["camera_id"], row["node_id"], row["doc"])
            cam = cam_cache[row["camera_id"]]
            rois = dict(cam.get("rois") or {})
            rois[row["node_id"]] = row["doc"]
            cam["rois"] = rois
            out.append(
                roi_item(
                    row["camera_id"],
                    row["node_id"],
                    row["doc"],
                    label=node_label(row["ntype"], row["priority"]),
                    kind=row["ntype"],
                    ref_width=self._ref_w,
                    ref_height=self._ref_h,
                )
            )
        return UseCaseResult.ok(items=out)


class DeleteRoi(_RoiWriteBase):
    async def execute(
        self,
        camera_id: Optional[int] = None,
        node_id: Optional[str] = None,
        roi_id: Optional[str] = None,
    ) -> UseCaseResult:
        gate = require_inference_paused(self._inference)
        if gate:
            return gate
        camera_id, node_id, fail = await self._resolve(camera_id, node_id, roi_id)
        if fail:
            return fail
        cam = await self._cameras.get_by_id(camera_id)
        if not cam:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)
        rois = cam.get("rois") or {}
        if node_id not in rois:
            return UseCaseResult.fail("ROI không tồn tại", http_status=404)
        pairs_deleted: List[str] = []
        if self._pairs is not None:
            pairs_deleted = await cascade_delete_pairs_for_node(self._pairs, node_id)
        await self._cameras.delete_roi(camera_id, node_id)
        return UseCaseResult.ok(
            id=f"{camera_id}:{node_id}",
            deleted=True,
            pairsDeleted=pairs_deleted,
        )
