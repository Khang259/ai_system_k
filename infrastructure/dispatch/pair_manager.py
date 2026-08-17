"""
PairManager — dispatch loop với Strategy Pattern.

HTTP ICS nằm ở DispatchGateway (infrastructure). Strategy chỉ build payload + gọi Port.
on_dispatch_success được inject từ composition root (không import service shim).
"""
from __future__ import annotations

import time
import threading
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple

from config.settings import settings
from application.dispatch.ics_payload import (
    build_double_payload,
    build_empty_payload,
    build_single_payload,
)
from application.ports import DispatchGateway
from domain.dispatch.pairing import build_dispatch_pairs
from utils.setup_log import setup_logger

logger = setup_logger("pair_manager", "logs/pair_manager/log")

OnDispatchSuccessFn = Callable[[str], None]


class DispatchStrategy(ABC):
    """Interface cho tất cả loại dispatch. Mỗi subclass implement execute()."""

    def __init__(self, gateway: DispatchGateway):
        self._gateway = gateway

    def post(self, payload: dict) -> bool:
        return self._gateway.send(payload)

    @abstractmethod
    def execute(
        self,
        pairs: List[Tuple[str, str]],
        pending_empty_queue: list,
        state_manager,
        snapshot_manager=None,
        on_dispatch_success: Optional[OnDispatchSuccessFn] = None,
    ) -> None:
        ...


class SingleDispatch(DispatchStrategy):
    """1 start → 1 end. Dùng cho runtime hiện tại."""

    def execute(
        self,
        pairs,
        pending_empty_queue,
        state_manager,
        snapshot_manager=None,
        on_dispatch_success=None,
    ):
        for start_point, end_point in pairs:
            payload = build_single_payload(start_point, end_point)
            order_id = payload.get("orderId")
            success = self.post(payload)
            logger.debug(
                f"[SINGLE] ({start_point} → {end_point}) orderId={order_id} success={success}"
            )

            if success:
                if snapshot_manager:
                    snapshot_manager.save_pair_snapshots(start_point, end_point, order_id)
                state_manager.set_pair_used(start_point, end_point, order_id, empty_car=False)
                if on_dispatch_success:
                    on_dispatch_success(start_point)
            else:
                logger.error(f"[SINGLE] Failed: ({start_point}, {end_point})")


class EmptyDispatch(DispatchStrategy):
    """start_empty → END cố định."""

    def execute(
        self,
        pairs,
        pending_empty_queue,
        state_manager,
        snapshot_manager=None,
        on_dispatch_success=None,
    ):
        now = time.time()
        while pending_empty_queue:
            start_empty, deadline = pending_empty_queue[0]
            if now <= deadline:
                break

            end_empty = settings.END_POINT_EMPTY
            payload = build_empty_payload(start_empty, end_empty)
            order_id = payload.get("orderId")
            success = self.post(payload)
            logger.debug(
                f"[EMPTY] ({start_empty} → {end_empty}) orderId={order_id} success={success}"
            )

            if success:
                if snapshot_manager:
                    snapshot_manager.save_pair_snapshots(start_empty, end_empty, order_id)
                state_manager.set_pair_used(start_empty, end_empty, order_id, empty_car=True)
            else:
                logger.error(f"[EMPTY] Failed: ({start_empty}, {end_empty})")

            pending_empty_queue.pop(0)


class DoubleDispatch(DispatchStrategy):
    """Ghép normal + empty → 1 lệnh double. Timeout empty → flush empty."""

    def execute(
        self,
        pairs,
        pending_empty_queue,
        state_manager,
        snapshot_manager=None,
        on_dispatch_success=None,
    ):
        now = time.time()
        normal_idx = 0

        while normal_idx < len(pairs) and pending_empty_queue:
            start_empty, deadline = pending_empty_queue[0]
            end_empty = settings.END_POINT_EMPTY

            if now > deadline:
                payload = build_empty_payload(start_empty, end_empty)
                order_id = payload.get("orderId")
                success = self.post(payload)
                logger.debug(f"[DOUBLE→EMPTY flush] ({start_empty}) orderId={order_id}")
                if success:
                    if snapshot_manager:
                        snapshot_manager.save_pair_snapshots(start_empty, end_empty, order_id)
                    state_manager.set_pair_used(start_empty, end_empty, order_id, empty_car=True)
                else:
                    logger.error(f"[DOUBLE] Empty flush failed: {start_empty}")
                pending_empty_queue.pop(0)
                continue

            start_point, end_point = pairs[normal_idx]
            payload = build_double_payload(start_point, end_point, start_empty, end_empty)
            order_id = payload.get("orderId")
            success = self.post(payload)
            logger.debug(
                f"[DOUBLE] ({start_point},{end_point})+({start_empty},{end_empty}) orderId={order_id}"
            )

            if success:
                if snapshot_manager:
                    snapshot_manager.save_pair_snapshots(start_point, end_point, order_id)
                state_manager.set_pair_used(start_point, end_point, order_id, empty_car=False)
                state_manager.set_pair_used(start_empty, end_empty, order_id, empty_car=True)
                if on_dispatch_success:
                    on_dispatch_success(start_point)
            else:
                logger.error(
                    f"[DOUBLE] Failed: ({start_point},{end_point})+({start_empty},{end_empty})"
                )

            pending_empty_queue.pop(0)
            normal_idx += 1

        for pair in pairs[normal_idx:]:
            start_point, end_point = pair
            payload = build_single_payload(start_point, end_point)
            order_id = payload.get("orderId")
            success = self.post(payload)
            logger.debug(f"[DOUBLE→SINGLE] ({start_point},{end_point}) orderId={order_id}")
            if success:
                if snapshot_manager:
                    snapshot_manager.save_pair_snapshots(start_point, end_point, order_id)
                state_manager.set_pair_used(start_point, end_point, order_id, empty_car=False)
                if on_dispatch_success:
                    on_dispatch_success(start_point)
            else:
                logger.error(f"[DOUBLE→SINGLE] Failed: ({start_point},{end_point})")

        while pending_empty_queue:
            start_empty, deadline = pending_empty_queue[0]
            if now <= deadline:
                break
            end_empty = settings.END_POINT_EMPTY
            payload = build_empty_payload(start_empty, end_empty)
            order_id = payload.get("orderId")
            success = self.post(payload)
            if success:
                state_manager.set_pair_used(start_empty, end_empty, order_id, empty_car=True)
            pending_empty_queue.pop(0)


class PairManager:
    def __init__(
        self,
        state_manager,
        validate_pairs,
        strategy: DispatchStrategy,
        snapshot_manager=None,
        on_dispatch_success: Optional[OnDispatchSuccessFn] = None,
    ):
        self.state_manager = state_manager
        self.validate_pairs = validate_pairs
        self.strategy = strategy
        self.snapshot_manager = snapshot_manager
        self.on_dispatch_success = on_dispatch_success
        self.pending_empty_queue: list = []
        self.running = False
        self.thread: Optional[threading.Thread] = None
        logger.info(f"PairManager initialized with strategy={strategy.__class__.__name__}")

    def make_pairs(self) -> Tuple[List, List]:
        now = time.time()

        for pair in self.validate_pairs:
            if len(pair) == 1:
                start_empty = pair[0]
                if start_empty in self.state_manager.ready_start_list:
                    if not any(start_empty == item[0] for item in self.pending_empty_queue):
                        self.pending_empty_queue.append(
                            (start_empty, now + settings.EMPTY_DEADLINE_SEC)
                        )

        pairs = build_dispatch_pairs(
            self.state_manager.ready_start_list,
            self.state_manager.ready_end_list,
            self.validate_pairs,
        )
        payloads = [
            build_single_payload(start_point, end_point)
            for start_point, end_point in pairs
        ]
        return pairs, payloads

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="PairManager")
        self.thread.start()
        logger.info("PairManager thread started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("PairManager thread stopped")

    def _run(self):
        logger.info("PairManager processing loop started")
        while self.running:
            try:
                self.state_manager.process_starts()
                self.state_manager.process_ends(warn=logger.warning)
                pairs, _ = self.make_pairs()
                self.strategy.execute(
                    pairs=pairs,
                    pending_empty_queue=self.pending_empty_queue,
                    state_manager=self.state_manager,
                    snapshot_manager=self.snapshot_manager,
                    on_dispatch_success=self.on_dispatch_success,
                )
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in pair processing loop: {e}", exc_info=True)
                time.sleep(1)


def get_validate_pairs(config_validate_pairs):
    return set(tuple(p) for p in config_validate_pairs)
