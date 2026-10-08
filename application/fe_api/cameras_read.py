"""Đọc camera / ROI list cho /api/v1."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.fe_api.mappers import camera_status, node_label, roi_item
from application.ports import CameraConfigRepository, CameraRuntime, NodeRepositoryPort
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

