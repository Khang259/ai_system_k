"""CRUD ROI trên camera."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.fe_api.mappers import node_label, parse_roi_id, roi_item, validate_box
from application.fe_api.sync_rules import (
    cascade_delete_node,
    cascade_delete_pairs_for_node,
    require_inference_paused,
)
from application.ports import (
    CameraConfigRepository,
    InferencePort,
    NodeRepositoryPort,
    PairsRepositoryPort,
)
from application.result import UseCaseResult


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
