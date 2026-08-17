"""
Batch scan policy — confirm-ready / auto-pause / new-node guard.

Pure functions: no camera manager, inference engine, or threading.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Set


@dataclass(frozen=True)
class BatchSnapshot:
    nodes: frozenset
    sum_request: int = 0
    active: bool = True

    @property
    def size(self) -> int:
        return len(self.nodes)

    @property
    def remaining(self) -> int:
        return self.size - self.sum_request


def start_batch(detected_nodes: Iterable[str]) -> BatchSnapshot:
    """Operator confirm-ready: snapshot hiện tại làm batch size."""
    return BatchSnapshot(nodes=frozenset(detected_nodes), sum_request=0, active=True)


def record_dispatch_success(batch: BatchSnapshot) -> BatchSnapshot:
    """Sau mỗi dispatch thành công — tăng sum_request."""
    if not batch.active:
        return batch
    return BatchSnapshot(
        nodes=batch.nodes,
        sum_request=batch.sum_request + 1,
        active=True,
    )


def should_auto_pause(batch: BatchSnapshot) -> bool:
    """True khi đã dispatch đủ (hoặc vượt) snapshot size."""
    return batch.active and batch.remaining <= 0


def find_new_nodes(
    current_detected: Iterable[str],
    snapshot_nodes: Iterable[str],
) -> Set[str]:
    """Node start đang có hàng nhưng không có trong snapshot ban đầu."""
    return set(current_detected) - set(snapshot_nodes)


def should_pause_for_new_nodes(
    current_detected: Iterable[str],
    snapshot_nodes: Iterable[str],
) -> Optional[Set[str]]:
    """
    Nếu có node mới ngoài snapshot → trả về set node đó (caller phải pause).
    Không có → None.
    """
    new_nodes = find_new_nodes(current_detected, snapshot_nodes)
    return new_nodes if new_nodes else None


def idle_batch() -> BatchSnapshot:
    """Trạng thái sau pause / hoàn thành batch."""
    return BatchSnapshot(nodes=frozenset(), sum_request=0, active=False)
