"""Helper dùng chung Create/Update camera + observedNodeIds."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.fe_api.priority_rules import (
    ensure_start_priority_unique,
    parse_optional_end_priority,
    parse_required_start_priority,
)
from application.ports import CameraConfigRepository, NodeRepositoryPort
from application.result import UseCaseResult


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


async def _priority_for_new_node(
    nodes: NodeRepositoryPort,
    nid: str,
    ntype: str,
    zone_s: str,
    node_priorities: Optional[Dict[str, int]],
    *,
    reserved: Dict[int, str],
) -> tuple[Optional[int], Optional[UseCaseResult]]:
    """
    Resolve priority khi create node.
    Start: bắt buộc + unique trong zone (DB + reserved trong batch).
    End: optional, mặc định 0.
    """
    if ntype == "start":
        p, err = parse_required_start_priority(nid, node_priorities)
        if err:
            return None, err
        assert p is not None
        if p in reserved:
            return None, UseCaseResult.fail(
                f"priority {p} trùng trong batch "
                f"(start {reserved[p]} và {nid})",
                http_status=409,
            )
        conflict = await ensure_start_priority_unique(nodes, zone_s, p)
        if conflict:
            return None, conflict
        reserved[p] = nid
        return p, None
    return parse_optional_end_priority(nid, node_priorities), None


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

