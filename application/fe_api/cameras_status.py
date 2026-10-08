"""Bật/tắt camera + cascade nodes/pairs."""
from __future__ import annotations

from application.fe_api.sync_rules import (
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

