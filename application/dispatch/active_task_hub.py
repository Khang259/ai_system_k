"""
Panel order đang chạy (RAM) + phát event SSE `dispatch.task` / `dispatch.task.removed`.

Thread-safe: PairManager gọi upsert() từ thread nền.
Mất khi restart app → nạp lại qua get_active_tasks / webhook.
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Dict, List, Tuple

from domain.dispatch.active_task import sort_active_tasks

TASK_EVENT = "dispatch.task"
TASK_REMOVED_EVENT = "dispatch.task.removed"

Event = Tuple[str, Dict[str, Any]]


class ActiveTaskHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, Dict[str, Any]] = {}
        self._subs: List[queue.Queue] = []

    def list_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            items = [dict(it) for it in self._items.values()]
        return sort_active_tasks(items)

    def upsert(self, item: Dict[str, Any]) -> None:
        with self._lock:
            self._items[item["orderId"]] = dict(item)
        self._publish((TASK_EVENT, dict(item)))

    def set_status(self, order_id: str, status: str) -> bool:
        """Đổi status order đã có. Không có → False."""
        with self._lock:
            item = self._items.get(order_id)
            if item is None:
                return False
            item = {**item, "status": status}
            self._items[order_id] = item
        self._publish((TASK_EVENT, dict(item)))
        return True

    def remove(self, order_id: str) -> None:
        with self._lock:
            self._items.pop(order_id, None)
        self._publish((TASK_REMOVED_EVENT, {"orderId": order_id}))

    def replace_all(self, items: List[Dict[str, Any]]) -> None:
        """Đồng bộ theo ICS: order không còn trong `items` bị xóa khỏi panel."""
        new_ids = {it["orderId"] for it in items}
        with self._lock:
            stale = [oid for oid in self._items if oid not in new_ids]
        for oid in stale:
            self.remove(oid)
        for it in items:
            self.upsert(it)

    def subscribe(self, maxsize: int = 256) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def _publish(self, event: Event) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                # Client chậm → bỏ event cũ nhất, giữ event mới
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass
