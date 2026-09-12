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
from application.ports import (
    CameraConfigRepository,
    CameraRuntime,
    NodeRepositoryPort,
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
    def __init__(
        self,
        cameras: CameraConfigRepository,
        runtime: CameraRuntime,
    ) -> None:
        self._cameras = cameras
        self._runtime = runtime

    async def execute(self, camera_id: int, enabled: bool) -> UseCaseResult:
        doc = await self._cameras.get_by_id(camera_id)
        if not doc:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)
        await self._cameras.set_enabled(camera_id, enabled)
        if self._runtime.is_ready():
            self._runtime.set_camera_enabled_by_id(camera_id, enabled)
        return UseCaseResult.ok(cameraId=camera_id, enabled=enabled)


class _RoiWriteBase:
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
        err = validate_box(box, self._ref_w, self._ref_h)
        if err:
            return UseCaseResult.fail(err, http_status=400)
        cam = await self._cameras.get_by_id(camera_id)
        if not cam:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)
        node = await self._nodes.get_by_id(node_id)
        if not node:
            return UseCaseResult.fail(f"Node {node_id} not found", http_status=404)
        ntype = node.get("node_type") or (
            "start" if node_id.startswith("start_") else "end"
        )
        ok = await self._cameras.upsert_roi(
            camera_id, node_id, self._roi_doc(box, ntype)
        )
        if not ok:
            # matched nhưng giá trị giống hệt → modified_count=0; vẫn coi là thành công
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
    async def execute(
        self,
        box: List[Any],
        camera_id: Optional[int] = None,
        node_id: Optional[str] = None,
        roi_id: Optional[str] = None,
    ) -> UseCaseResult:
        err = validate_box(box, self._ref_w, self._ref_h)
        if err:
            return UseCaseResult.fail(err, http_status=400)
        camera_id, node_id, fail = await self._resolve(camera_id, node_id, roi_id)
        if fail:
            return fail
        cam = await self._cameras.get_by_id(camera_id)
        if not cam:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)
        rois = cam.get("rois") or {}
        if node_id not in rois:
            return UseCaseResult.fail("ROI không tồn tại", http_status=404)
        node = await self._nodes.get_by_id(node_id)
        ntype = (node or {}).get("node_type") or (
            "start" if node_id.startswith("start_") else "end"
        )
        doc = self._roi_doc(box, ntype)
        await self._cameras.upsert_roi(camera_id, node_id, doc)
        item = roi_item(
            camera_id,
            node_id,
            doc,
            label=node_label(ntype, (node or {}).get("priority", 0)),
            kind=ntype,
            ref_width=self._ref_w,
            ref_height=self._ref_h,
        )
        return UseCaseResult.ok(**item)


class DeleteRoi(_RoiWriteBase):
    async def execute(
        self,
        camera_id: Optional[int] = None,
        node_id: Optional[str] = None,
        roi_id: Optional[str] = None,
    ) -> UseCaseResult:
        camera_id, node_id, fail = await self._resolve(camera_id, node_id, roi_id)
        if fail:
            return fail
        cam = await self._cameras.get_by_id(camera_id)
        if not cam:
            return UseCaseResult.fail(f"Camera {camera_id} not found", http_status=404)
        rois = cam.get("rois") or {}
        if node_id not in rois:
            return UseCaseResult.fail("ROI không tồn tại", http_status=404)
        await self._cameras.delete_roi(camera_id, node_id)
        return UseCaseResult.ok(id=f"{camera_id}:{node_id}", deleted=True)
