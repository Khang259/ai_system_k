"""
Hub phát event runtime node (detected / isReady / lock) cho SSE.

Thread-safe: CameraProcessor / PairManager gọi touch() từ thread khác.
Debounce gom nhiều đổi → một flush.
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Dict, List, Optional, Set


def map_runtime_item(node_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else {}
    return {
        "nodeId": node_id,
        "detected": bool(data.get("detected", data.get("state", False))),
        "isReady": bool(data.get("isReady", False)),
        "lock": {
            "user": bool(lock.get("user", False)),
            "system": bool(lock.get("system", False)),
            "orderId": lock.get("orderId"),
        },
    }


class RuntimeStateHub:
    def __init__(self, debounce_ms: float = 150.0) -> None:
        self._debounce_sec = max(0.05, float(debounce_ms) / 1000.0)
        self._pending: Set[str] = set()
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._subs: List[queue.Queue] = []
        self._snapshot_fn: Optional[Callable[[], Dict[str, Dict[str, Any]]]] = None

    def bind_snapshot(self, fn: Callable[[], Dict[str, Dict[str, Any]]]) -> None:
        self._snapshot_fn = fn

    def touch(self, *node_ids: str) -> None:
        ids = [n for n in node_ids if n]
        if not ids:
            return
        with self._lock:
            self._pending.update(ids)
            if self._timer is not None:
                self._timer.cancel()
            t = threading.Timer(self._debounce_sec, self._flush)
            t.daemon = True
            self._timer = t
            t.start()

    def subscribe(self, maxsize: int = 256) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def _flush(self) -> None:
        with self._lock:
            pending = list(self._pending)
            self._pending.clear()
            subs = list(self._subs)
            self._timer = None
        if not pending or not subs:
            return
        snap_fn = self._snapshot_fn
        snap = snap_fn() if snap_fn else {}
        events: List[Dict[str, Any]] = []
        for nid in pending:
            raw = snap.get(nid)
            if raw is None:
                continue
            events.append(map_runtime_item(nid, raw))
        if not events:
            return
        for q in subs:
            for ev in events:
                try:
                    q.put_nowait(ev)
                except queue.Full:
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        q.put_nowait(ev)
                    except queue.Full:
                        pass
