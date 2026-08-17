"""Priority helpers for start-node ordering."""

from __future__ import annotations

from domain.settings import PRIORITY_FALLBACK


def get_node_priority(node_id: str) -> int:
    """
    Extract priority from node_id.
    Default: numeric digits in node_id, ascending = higher priority.

    Example: start_10001050 → 10001050
    """
    digits = "".join(filter(str.isdigit, node_id))
    return int(digits) if digits else PRIORITY_FALLBACK
