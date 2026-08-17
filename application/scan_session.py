"""In-memory batch scan session — application state, không I/O."""
from __future__ import annotations

import threading

from domain.batch_policy import BatchSnapshot, idle_batch, record_dispatch_success, start_batch


class ScanSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._batch = idle_batch()

    def reset(self) -> None:
        with self._lock:
            self._batch = idle_batch()

    def start(self, detected_nodes) -> BatchSnapshot:
        with self._lock:
            self._batch = start_batch(detected_nodes)
            return self._batch

    def record_success(self) -> BatchSnapshot:
        with self._lock:
            self._batch = record_dispatch_success(self._batch)
            return self._batch

    def get(self) -> BatchSnapshot:
        with self._lock:
            return self._batch
