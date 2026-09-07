"""
PairManager — dispatch loop (infrastructure).

Thread nền gọi DispatchService mỗi ~1s. Strategy pattern để chọn single/empty/double.
"""
from __future__ import annotations

import time
import threading
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple

from config.settings import settings
from application.dispatch.dispatch_service import DispatchService
from application.ports import DispatchGateway
from utils.setup_log import setup_logger

logger = setup_logger("pair_manager", "logs/pair_manager/log")

OnDispatchSuccessFn = Callable[[str], None]


class DispatchStrategy(ABC):
    """Interface cho tất cả loại dispatch. Wrapper DispatchService."""

    def __init__(self, service: DispatchService):
        self._service = service

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
        self._service.dispatch_single(
            pairs,
            state_manager,
            snapshot_manager=snapshot_manager,
            on_dispatch_success=on_dispatch_success,
        )


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
        self._service.dispatch_empty(
            pending_empty_queue,
            settings.END_POINT_EMPTY,
            now,
            state_manager,
            snapshot_manager=snapshot_manager,
        )


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
        self._service.dispatch_double(
            pairs,
            pending_empty_queue,
            settings.END_POINT_EMPTY,
            now,
            state_manager,
            snapshot_manager=snapshot_manager,
            on_dispatch_success=on_dispatch_success,
        )


class PairManager:
    def __init__(
        self,
        state_manager,
        validate_pairs,
        strategy,
        dispatch_service: DispatchService,
        snapshot_manager=None,
        on_dispatch_success: Optional[OnDispatchSuccessFn] = None,
    ):
        self.state_manager = state_manager
        self.validate_pairs = validate_pairs
        self.strategy = strategy
        self.dispatch_service = dispatch_service
        self.snapshot_manager = snapshot_manager
        self.on_dispatch_success = on_dispatch_success
        self.pending_empty_queue = []
        self.running = False
        self.thread = None
        logger.info(f"PairManager initialized with strategy={strategy.__class__.__name__}")

    def make_pairs(self) -> Tuple[List, List]:
        """Build (pairs, empty) từ state_manager + validate_pairs."""
        now = time.time()

        for pair in self.validate_pairs:
            if len(pair) == 1:
                start_empty = pair[0]
                if start_empty in self.state_manager.ready_start_list:
                    if not any(start_empty == item[0] for item in self.pending_empty_queue):
                        self.pending_empty_queue.append(
                            (start_empty, now + settings.EMPTY_DEADLINE_SEC)
                        )

        pairs = self.dispatch_service.build_pairs(self.state_manager)
        
        empty_list = [
            (pair[0],)
            for pair in self.validate_pairs
            if len(pair) == 1 and pair[0] in self.state_manager.ready_starts()
        ]
        return pairs, empty_list

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
