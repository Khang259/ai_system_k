"""Rules: start priority bắt buộc + unique trong từng zone."""
from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports import NodeRepositoryPort
from application.result import UseCaseResult


async def find_start_conflict(
    nodes: NodeRepositoryPort,
    zone_id: str,
    priority: int,
    *,
    exclude_node_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Trả start khác đang giữ (zone, priority), hoặc None."""
    conflict = await nodes.find_start_by_zone_priority(zone_id, priority)
    if not conflict:
        return None
    other = conflict.get("node_id")
    if exclude_node_id and other == exclude_node_id:
        return None
    return conflict


async def ensure_start_priority_unique(
    nodes: NodeRepositoryPort,
    zone_id: str,
    priority: int,
    *,
    exclude_node_id: Optional[str] = None,
) -> Optional[UseCaseResult]:
    """None = OK; UseCaseResult = lỗi 409."""
    z = (zone_id or "").strip().upper()
    if not z:
        return UseCaseResult.fail(
            "zone bắt buộc khi gán priority cho start",
            http_status=400,
        )
    conflict = await find_start_conflict(
        nodes, z, priority, exclude_node_id=exclude_node_id
    )
    if conflict:
        other = conflict.get("node_id")
        return UseCaseResult.fail(
            f"priority {priority} đã dùng bởi start {other} trong zone {z}",
            http_status=409,
        )
    return None


def parse_required_start_priority(
    node_id: str,
    node_priorities: Optional[Dict[str, int]],
) -> tuple[Optional[int], Optional[UseCaseResult]]:
    """Start mới tạo: bắt buộc có trong nodePriorities."""
    if not node_priorities or node_id not in node_priorities:
        return None, UseCaseResult.fail(
            f"start {node_id} cần nodePriorities[\"{node_id}\"]",
            http_status=400,
        )
    try:
        p = int(node_priorities[node_id])
    except (TypeError, ValueError):
        return None, UseCaseResult.fail(
            f"priority của {node_id} không hợp lệ",
            http_status=400,
        )
    if p < 0:
        return None, UseCaseResult.fail(
            "priority phải >= 0",
            http_status=400,
        )
    return p, None


def parse_optional_end_priority(
    node_id: str,
    node_priorities: Optional[Dict[str, int]],
) -> int:
    """End: lấy từ map nếu có, mặc định 0 (không unique)."""
    if not node_priorities or node_id not in node_priorities:
        return 0
    try:
        p = int(node_priorities[node_id])
    except (TypeError, ValueError):
        return 0
    return max(0, p)
