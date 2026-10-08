"""Pure pairing rules — no ICS / HTTP / threads."""

from __future__ import annotations

from collections import deque
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from domain.dispatch.priority import StartMetaMap, start_sort_key

Pair = Tuple[str, str]


def build_dispatch_pairs(
    ready_starts: Iterable[str],
    ready_ends: Set[str],
    validate_pairs: Sequence[Sequence[str]],
    start_meta: Optional[StartMetaMap] = None,
) -> List[Pair]:
    """
    Build (start, end) list from ready sets and allowed validate_pairs.

    - Only pairs with len == 2 are considered (empty-only pairs handled elsewhere).
    - Starts sorted by Mongo priority ASC, then zone_id, then node_id.
    - Each start/end is used at most once per call.
    """
    pairs: List[Pair] = []
    sorted_starts = sorted(
        ready_starts,
        key=lambda nid: start_sort_key(nid, start_meta),
    )
    start_queue = deque(sorted_starts)

    used_starts: Set[str] = set()
    used_ends: Set[str] = set()

    while start_queue:
        start_point = start_queue.popleft()
        if start_point in used_starts:
            continue

        candidate_end = None
        for pair in validate_pairs:
            if len(pair) != 2:
                continue
            start_id, end_id = pair[0], pair[1]
            if start_id != start_point:
                continue
            if end_id in ready_ends and end_id not in used_ends:
                candidate_end = end_id
                break

        if candidate_end is None:
            continue

        pairs.append((start_point, candidate_end))
        used_starts.add(start_point)
        used_ends.add(candidate_end)

    return pairs
