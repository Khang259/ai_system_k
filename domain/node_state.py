"""
Domain node state — ready lists, locks, order mapping.

Pure Python. Timer kwargs default = domain.settings (test / no inject).
Production: RuntimeService inject từ config.settings (.env thắng).

RAM mirror Mongo field `lock`:
  lock_user / lock_system / lock_order_id
`flag` = blocked = lock_user OR lock_system (tương thích process/ready cũ).
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple

from domain.settings import (
    END_FLAG_RESET_AFTER_SEC,
    END_READY_AFTER_SEC,
    START_READY_AFTER_SEC,
)

PointData = Dict[str, Any]
OrderPair = Tuple[str, str, bool]  # start, end, empty_car


def _refresh_flag(data: PointData) -> None:
    data["flag"] = bool(data.get("lock_user") or data.get("lock_system"))


def _is_blocked(data: PointData) -> bool:
    return bool(data.get("lock_user") or data.get("lock_system") or data.get("flag"))


class NodeState:
    def __init__(
        self,
        validate_pairs,
        *,
        start_ready_after_sec: int = START_READY_AFTER_SEC,
        end_ready_after_sec: int = END_READY_AFTER_SEC,
        end_flag_reset_after_sec: int = END_FLAG_RESET_AFTER_SEC,
        time_fn=time.time,
    ):
        self.validate_pairs = validate_pairs
        self.start_ready_after_sec = start_ready_after_sec
        self.end_ready_after_sec = end_ready_after_sec
        self.end_flag_reset_after_sec = end_flag_reset_after_sec
        self._time = time_fn

        self.points: DefaultDict[str, PointData] = defaultdict(
            lambda: {
                "state": False,
                "time": self._time(),
                "flag": False,
                "lock_user": False,
                "lock_system": False,
                "lock_order_id": None,
                "frame": None,
            }
        )
        self.ready_start_list: Set[str] = set()
        self.ready_end_list: Set[str] = set()
        self.pair_mapping: Dict[str, str] = {}
        # {orderId: [(start_point, end_point, empty_car), ...]}
        self.order_mapping: Dict[str, List[OrderPair]] = {}

    def get_state_nodes(self, node_id: str, state: bool, frame=None) -> None:
        current = self.points[node_id]
        old_state = current["state"]
        current["state"] = state
        if frame is not None:
            current["frame"] = frame

        if old_state == state:
            return

        now = self._time()
        if node_id.startswith("start_"):
            current["time"] = now
            if not state:
                self.ready_start_list.discard(node_id)
        elif node_id.startswith("end_"):
            current["time"] = now
            if state:
                self.ready_end_list.discard(node_id)

    def process_starts(self) -> None:
        current_time = self._time()
        for node_id, data in list(self.points.items()):
            if not node_id.startswith("start_"):
                continue
            if data["state"] and not _is_blocked(data):
                existed_time = current_time - data["time"]
                if existed_time > self.start_ready_after_sec:
                    self.ready_start_list.add(node_id)

    def process_ends(self, warn=None) -> List[str]:
        """
        Returns: node_id vừa mất system-lock do timeout (để sync Mongo).
        """
        cleared_system: List[str] = []
        current_time = self._time()
        for node_id, data in list(self.points.items()):
            if not node_id.startswith("end_"):
                continue

            if not data["state"]:
                if not _is_blocked(data):
                    existed_time = current_time - data["time"]
                    if existed_time > self.end_ready_after_sec:
                        self.ready_end_list.add(node_id)
                continue

            # End có hàng trở lại trong khi đang system-lock → timeout reset pair
            if data.get("lock_system") or data.get("flag"):
                existed_time = current_time - data["time"]
                if existed_time > self.end_flag_reset_after_sec:
                    self.ready_end_list.discard(node_id)
                    start_point = self.pair_mapping.get(node_id)
                    if start_point:
                        self.ready_start_list.discard(start_point)
                        cleared_system.extend(
                            self.clear_system_lock(node_id, start_point)
                        )
                        del self.pair_mapping[node_id]
                    else:
                        if warn:
                            warn(
                                f"No start_point found in pair_mapping for {node_id}"
                            )
                        cleared_system.extend(self.clear_system_lock(node_id))

        return cleared_system

    def set_pair_used(
        self,
        start_point: str,
        end_point: str,
        order_id: str,
        empty_car: bool = False,
    ) -> None:
        for nid in (start_point, end_point):
            self.points[nid]["lock_system"] = True
            self.points[nid]["lock_order_id"] = order_id
            _refresh_flag(self.points[nid])
        self.ready_start_list.discard(start_point)
        self.ready_end_list.discard(end_point)
        self.pair_mapping[end_point] = start_point
        pairs = self.order_mapping.setdefault(order_id, [])
        pairs.append((start_point, end_point, empty_car))

    def set_user_lock(self, node_id: str, enabled: bool) -> bool:
        """User lock. Tắt lock → reset timer (chờ lại ready)."""
        if node_id not in self.points and not enabled:
            # vẫn cho phép tạo point khi hydrate
            pass
        data = self.points[node_id]
        data["lock_user"] = bool(enabled)
        _refresh_flag(data)
        self.discard_from_ready(node_id)
        if not enabled:
            data["time"] = self._time()
        return bool(enabled)

    def apply_persisted_lock(
        self,
        node_id: str,
        *,
        user: bool = False,
        system: bool = False,
        order_id: Optional[str] = None,
    ) -> None:
        """Hydrate / đồng bộ từ Mongo — không ghi DB."""
        data = self.points[node_id]
        was_blocked = _is_blocked(data)
        data["lock_user"] = bool(user)
        data["lock_system"] = bool(system)
        data["lock_order_id"] = order_id if system else None
        _refresh_flag(data)
        self.discard_from_ready(node_id)
        if was_blocked and not _is_blocked(data):
            # Mở khóa → chờ lại timer ready
            data["time"] = self._time()


    def clear_system_lock(self, *node_ids: str) -> List[str]:
        cleared: List[str] = []
        for nid in node_ids:
            if not nid or nid not in self.points:
                continue
            data = self.points[nid]
            if data.get("lock_system"):
                cleared.append(nid)
            data["lock_system"] = False
            data["lock_order_id"] = None
            _refresh_flag(data)
            self.discard_from_ready(nid)
            data["time"] = self._time()
        return cleared

    def clear_system_by_order_id(self, order_id: str) -> List[str]:
        if not order_id:
            return []
        ids = [
            nid
            for nid, data in self.points.items()
            if data.get("lock_system") and data.get("lock_order_id") == order_id
        ]
        return self.clear_system_lock(*ids)

    def clear_user_lock(self, node_id: str) -> None:
        self.set_user_lock(node_id, False)

    def discard_from_ready(self, node_id: str) -> None:
        self.ready_start_list.discard(node_id)
        self.ready_end_list.discard(node_id)

    def get_detected_start_nodes(self) -> Set[str]:
        return {
            nid
            for nid, data in self.points.items()
            if nid.startswith("start_") and data.get("state") is True
        }

    def snapshot_points(self) -> Dict[str, Dict[str, Any]]:
        return {
            nid: {
                "state": bool(data["state"]),
                "flag": bool(data["flag"]),
                "lock": {
                    "user": bool(data.get("lock_user")),
                    "system": bool(data.get("lock_system")),
                    "orderId": data.get("lock_order_id"),
                },
            }
            for nid, data in self.points.items()
        }

    def lock_view(self, node_id: str) -> Dict[str, Any]:
        data = self.points.get(node_id) or {}
        return {
            "user": bool(data.get("lock_user")),
            "system": bool(data.get("lock_system")),
            "orderId": data.get("lock_order_id"),
        }
