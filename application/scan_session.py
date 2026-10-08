"""In-memory batch dispatch session — application state, không I/O."""
from __future__ import annotations

import threading
from typing import Any, Dict, Iterable, Optional

from domain.batch_policy import BatchSnapshot, idle_batch, record_dispatch_success, start_batch

# Lý do cổng gửi đóng — FE hiển thị cho người dùng
STOP_BATCH_COMPLETE = "batch_complete"
STOP_NEW_NODES = "new_nodes"
STOP_CANCELED = "canceled"


class ScanSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._batch = idle_batch()
        self._stop_reason: Optional[str] = None
        self._new_nodes: frozenset = frozenset()

    def reset(self, reason: Optional[str] = None, new_nodes: Iterable[str] = ()) -> None:
        with self._lock:
            self._batch = idle_batch()
            self._stop_reason = reason
            self._new_nodes = frozenset(new_nodes)

    def start(self, ready_nodes) -> BatchSnapshot:
        with self._lock:
            self._batch = start_batch(ready_nodes)
            self._stop_reason = None
            self._new_nodes = frozenset()
            return self._batch

    def record_success(self, node_id: Optional[str] = None) -> BatchSnapshot:
        with self._lock:
            self._batch = record_dispatch_success(self._batch, node_id)
            return self._batch

    def get(self) -> BatchSnapshot:
        with self._lock:
            return self._batch

    def status(self) -> Dict[str, Any]:
        with self._lock:
            batch = self._batch
            return {
                "active": batch.active,
                "size": batch.size,
                "nodes": sorted(batch.nodes),
                "dispatched": sorted(batch.dispatched),
                "remaining": max(batch.remaining, 0) if batch.active else 0,
                "stopReason": self._stop_reason,
                "newNodes": sorted(self._new_nodes),
            }
