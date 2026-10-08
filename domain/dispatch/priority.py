"""Priority helpers for start-node ordering (Mongo field, not node_id digits)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from domain.settings import PRIORITY_FALLBACK

# node_id -> { "priority": int|None, "zone_id": str }
StartMetaMap = Mapping[str, Mapping[str, Any]]


def resolve_priority(raw: Any) -> int:
    """Mongo priority → int; thiếu / invalid → PRIORITY_FALLBACK."""
    if raw is None:
        return PRIORITY_FALLBACK
    try:
        return int(raw)
    except (TypeError, ValueError):
        return PRIORITY_FALLBACK


def start_meta_from_docs(docs: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Node docs Mongo → StartMetaMap (chỉ start)."""
    meta: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        if (doc.get("node_type") or "").lower() != "start":
            continue
        nid = doc.get("node_id")
        if not nid:
            continue
        meta[str(nid)] = {
            "priority": doc.get("priority"),
            "zone_id": doc.get("zone_id") or "",
        }
    return meta


def start_sort_key(
    node_id: str,
    start_meta: Optional[StartMetaMap] = None,
) -> Tuple[int, str, str]:
    """
    Sort key: priority ASC, rồi zone_id, rồi node_id (tie-break kỹ thuật).

    Cùng priority khác zone → thứ tự ổn định, không mang nghĩa nghiệp vụ.
    """
    meta = (start_meta or {}).get(node_id) or {}
    priority = resolve_priority(meta.get("priority"))
    zone_id = str(meta.get("zone_id") or "")
    return (priority, zone_id, node_id)
