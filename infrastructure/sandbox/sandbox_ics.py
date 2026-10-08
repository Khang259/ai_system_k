"""
ICS giả cho sandbox — implement DispatchGateway (send) + IcsOrderQueryPort (get_order_list).

Ghi lại lệnh theo thứ tự nhận (`seq`) để đối chiếu priority.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from domain.dispatch.active_task import parse_order_id
from domain.models import OrderStatus
from infrastructure.sandbox.smoke_trail import emit, node_runtime_view
from utils.setup_log import setup_logger

logger = setup_logger("sandbox", "logs/sandbox/log")


class SandboxIcs:
    def __init__(self, state_provider=None) -> None:
        """state_provider: callable → NodeStateStore | None (snapshot lúc dispatch)."""
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._state_provider = state_provider

    def bind_state_provider(self, provider) -> None:
        self._state_provider = provider

    def send(self, payload: Dict[str, Any]) -> bool:
        order_id = str(payload.get("orderId"))
        with self._lock:
            seq = len(self._orders) + 1
            self._orders[order_id] = {
                "seq": seq,
                "orderId": order_id,
                "taskPath": [d.get("taskPath") for d in payload.get("taskOrderDetail") or []],
                "status": int(OrderStatus.ASSIGNED),
                "sentAt": time.time(),
            }
        logger.info(f"[SANDBOX ICS] nhận lệnh {order_id}")

        start_id: Optional[str] = None
        end_id: Optional[str] = None
        parsed = parse_order_id(order_id)
        if parsed:
            start_id, end_id = parsed
        state = self._state_provider() if self._state_provider else None
        emit(
            "system",
            "dispatch",
            seq=seq,
            orderId=order_id,
            startNodeId=start_id,
            endNodeId=end_id,
            taskPath=[d.get("taskPath") for d in payload.get("taskOrderDetail") or []],
            nodes=node_runtime_view(state, start_id or "", end_id or ""),
            hint="Hệ thống tự ghép cặp từ ready start/end — đối chiếu seq với thứ tự seed",
        )
        return True

    def get_order_list(self, area_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"OrderId": o["orderId"], "OrderStatus": o["status"]}
                for o in self._orders.values()
            ]

    def set_status(self, order_id: str, status: int) -> bool:
        with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                return False
            order["status"] = int(status)
        return True

    def get_orders(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(o) for o in self._orders.values()]
