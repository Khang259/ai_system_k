"""Luật sync cameras → nodes → pairs (camera SSOT identity).

Xóa node: cascade_delete_node — caller là UpdateCamera (observed replace-set)
hoặc DeleteCamera. Không còn route delete_node.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from application.ports import (
    CameraConfigRepository,
    InferencePort,
    NodeRepositoryPort,
    NodeStateStore,
    PairsRepositoryPort,
)
from application.result import UseCaseResult


MSG_INFERENCE_RUNNING = (
    "Tắt inference trước khi chỉnh cấu hình (pause-scan / stop)"
)


def require_inference_paused(inference: Optional[InferencePort]) -> Optional[UseCaseResult]:
    """
    Cho phép ghi config khi runtime chưa sẵn sàng hoặc inference đang pause.
    Chặn khi inference đang chạy (paused=False).
    """
    if inference is None or not inference.is_ready():
        return None
    paused = inference.is_paused()
    if paused is False:
        return UseCaseResult.fail(MSG_INFERENCE_RUNNING, http_status=409)
    return None


async def cascade_delete_pairs_for_node(
    pairs: PairsRepositoryPort,
    node_id: str,
) -> List[str]:
    """Xóa mọi pair chứa node. Trả list pair id đã xóa."""
    deleted: List[str] = []
    for doc in await pairs.list_containing_node(node_id):
        start = doc.get("start_point") or ""
        end = doc.get("end_point")
        ok = await pairs.delete(start, end)
        if ok:
            deleted.append(f"{start}:{end or '_'}")
    return deleted


async def cascade_delete_node(
    *,
    nodes: NodeRepositoryPort,
    cameras: CameraConfigRepository,
    pairs: PairsRepositoryPort,
    state: Optional[NodeStateStore],
    node_id: str,
) -> Dict[str, Any]:
    """
    Xóa pair → ROI → node. Trả stats.
    Caller đã kiểm tra node tồn tại (hoặc bỏ qua nếu không có).
    """
    nid = (node_id or "").strip()
    node = await nodes.get_by_id(nid)
    if not node:
        return {
            "nodeId": nid,
            "deleted": False,
            "pairsDeleted": [],
            "roiDeleted": False,
        }

    pairs_deleted = await cascade_delete_pairs_for_node(pairs, nid)

    camera_id = node.get("camera_id")
    roi_deleted = False
    if camera_id is not None:
        cam = await cameras.get_by_id(int(camera_id))
        rois = (cam or {}).get("rois") or {}
        if nid in rois:
            await cameras.delete_roi(int(camera_id), nid)
            roi_deleted = True

    await nodes.delete_by_node_id(nid)
    if state is not None and state.is_ready():
        state.discard_from_ready(nid)

    return {
        "nodeId": nid,
        "deleted": True,
        "pairsDeleted": pairs_deleted,
        "roiDeleted": roi_deleted,
    }


async def set_pairs_enabled_for_nodes(
    pairs: PairsRepositoryPort,
    node_ids: Set[str],
    enabled: bool,
) -> int:
    """Bật/tắt mọi pair chứa bất kỳ node trong set. Trả số pair cập nhật."""
    if not node_ids:
        return 0
    seen = set()
    count = 0
    for nid in node_ids:
        for doc in await pairs.list_containing_node(nid):
            start = doc.get("start_point") or ""
            end = doc.get("end_point")
            key = (start, end)
            if key in seen:
                continue
            seen.add(key)
            if await pairs.set_enabled(start, end, enabled):
                count += 1
    return count


async def require_node_ready_for_pair(
    nodes: NodeRepositoryPort,
    cameras: CameraConfigRepository,
    node_id: str,
    role: str,
) -> Optional[UseCaseResult]:
    """
    Node phải tồn tại, gắn đúng 1 camera, và có ROI trên camera đó.
    """
    node = await nodes.get_by_id(node_id)
    if not node:
        return UseCaseResult.fail(
            f"{role} node {node_id} không tồn tại", http_status=404
        )
    camera_id = node.get("camera_id")
    if camera_id is None:
        return UseCaseResult.fail(
            f"{role} node {node_id} chưa gắn camera — thêm vào observedNodeIds trước",
            http_status=400,
        )
    cam = await cameras.get_by_id(int(camera_id))
    if not cam:
        return UseCaseResult.fail(
            f"{role} node {node_id}: camera {camera_id} không tồn tại",
            http_status=400,
        )
    rois = cam.get("rois") or {}
    if node_id not in rois:
        return UseCaseResult.fail(
            f"{role} node {node_id} chưa có ROI trên camera {camera_id}",
            http_status=400,
        )
    return None
