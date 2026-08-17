"""
Domain node state — ready lists, flags, order mapping.

Pure Python. Timing thresholds come from domain.settings (defaults)
or injected by composition root (config override).
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
            if data["state"] and not data["flag"]:
                existed_time = current_time - data["time"]
                if existed_time > self.start_ready_after_sec:
                    self.ready_start_list.add(node_id)

    def process_ends(self, warn=None) -> None:
        current_time = self._time()
        for node_id, data in list(self.points.items()):
            if not node_id.startswith("end_"):
                continue

            if not data["state"]:
                if not data["flag"]:
                    existed_time = current_time - data["time"]
                    if existed_time > self.end_ready_after_sec:
                        self.ready_end_list.add(node_id)
                continue

            # End có hàng trở lại trong khi đang flag → timeout reset pair
            if data["flag"]:
                existed_time = current_time - data["time"]
                if existed_time > self.end_flag_reset_after_sec:
                    self.ready_end_list.discard(node_id)
                    start_point = self.pair_mapping.get(node_id)
                    if start_point:
                        self.ready_start_list.discard(start_point)
                        self.points[node_id]["flag"] = False
                        self.points[start_point]["flag"] = False
                        del self.pair_mapping[node_id]
                    else:
                        if warn:
                            warn(
                                f"No start_point found in pair_mapping for {node_id}"
                            )
                        self.points[node_id]["flag"] = False

    def set_pair_used(
        self,
        start_point: str,
        end_point: str,
        order_id: str,
        empty_car: bool = False,
    ) -> None:
        self.points[start_point]["flag"] = True
        self.points[end_point]["flag"] = True
        self.ready_start_list.discard(start_point)
        self.ready_end_list.discard(end_point)
        self.pair_mapping[end_point] = start_point
        pairs = self.order_mapping.setdefault(order_id, [])
        pairs.append((start_point, end_point, empty_car))

    def toggle_flag(self, node_id: str) -> Optional[bool]:
        if node_id not in self.points:
            return None
        current = self.points[node_id]["flag"]
        self.points[node_id]["flag"] = not current
        return not current

    def discard_from_ready(self, node_id: str) -> None:
        self.ready_start_list.discard(node_id)
        self.ready_end_list.discard(node_id)

    def get_detected_start_nodes(self) -> Set[str]:
        return {
            nid
            for nid, data in self.points.items()
            if nid.startswith("start_") and data.get("state") is True
        }

    def snapshot_points(self) -> Dict[str, Dict[str, bool]]:
        return {
            nid: {"state": bool(data["state"]), "flag": bool(data["flag"])}
            for nid, data in self.points.items()
        }
