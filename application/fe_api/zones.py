"""Zone use cases cho /api/v1."""
from __future__ import annotations

from typing import Any, Dict, List

from application.ports import (
    CameraConfigRepository,
    CameraRuntime,
    NodeRepositoryPort,
    ZoneRepositoryPort,
)
from application.result import UseCaseResult


class GetZones:
    def __init__(
        self,
        zones: ZoneRepositoryPort,
        cameras: CameraConfigRepository,
        nodes: NodeRepositoryPort,
        runtime: CameraRuntime,
    ) -> None:
        self._zones = zones
        self._cameras = cameras
        self._nodes = nodes
        self._runtime = runtime

    async def execute(self) -> UseCaseResult:
        zone_docs = await self._zones.get_all()
        all_cams = await self._cameras.get_all()
        all_nodes = await self._nodes.get_all()

        # zone → cameraIds (Mongo)
        cams_by_zone: Dict[str, List[Dict[str, Any]]] = {}
        for cam in all_cams:
            z = (cam.get("zone_id") or "").upper()
            cams_by_zone.setdefault(z, []).append(cam)

        nodes_by_zone: Dict[str, int] = {}
        for node in all_nodes:
            z = (node.get("zone_id") or "").upper()
            nodes_by_zone[z] = nodes_by_zone.get(z, 0) + 1

        # RAM enabled theo cameraId
        ram_enabled: Dict[int, bool] = {}
        if self._runtime.is_ready():
            for row in self._runtime.get_status().get("cameras") or []:
                cid = row.get("cameraId")
                if cid is not None:
                    ram_enabled[int(cid)] = bool(row.get("enabled"))

        items: List[Dict[str, Any]] = []
        for doc in zone_docs:
            zid = (doc.get("zone_id") or "").upper()
            zone_cams = cams_by_zone.get(zid, [])
            is_running = False
            for cam in zone_cams:
                cid = cam.get("cameraId")
                if cid is not None and ram_enabled.get(int(cid)):
                    is_running = True
                    break
            items.append(
                {
                    "id": zid,
                    "name": doc.get("name") or zid,
                    "isRunning": is_running,
                    "isConfigEnabled": bool(doc.get("enabled", True)),
                    "cameraCount": len(zone_cams),
                    "nodeCount": nodes_by_zone.get(zid, 0),
                    "lastChangedAt": None,
                    "lastChangedBy": None,
                }
            )
        return UseCaseResult.ok(items=items)
