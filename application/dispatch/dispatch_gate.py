"""
Cổng gửi ICS — PairManager gọi mỗi vòng trước khi dispatch.

Đóng khi chưa confirm-dispatch / batch xong.
Không halt khi có start ready ngoài batch (chờ confirm sau).

Strict order theo col trong zone; hole (head ∉ batch) → skip phần còn lại của col.
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence, Set, Tuple

from application.scan_session import STOP_BATCH_COMPLETE, ScanSession
from domain.batch_policy import (
    busy_zones,
    plan_col_dispatch,
    should_auto_pause,
)
from domain.dispatch.priority import StartMetaMap
from infrastructure.sandbox.smoke_trail import emit
from utils.setup_log import setup_logger

logger = setup_logger("dispatch_gate", "logs/dispatch_gate/log")


class DispatchGate:
    def __init__(
        self,
        scan: ScanSession,
        start_meta: Optional[Callable[[], StartMetaMap]] = None,
    ) -> None:
        self._scan = scan
        self._start_meta = start_meta or (lambda: {})

    def trusted_starts(self) -> Optional[Set[str]]:
        """Pending batch nodes khi cổng mở — PairManager dùng để trust pairing."""
        batch = self._scan.get()
        if not batch.active:
            return None
        return set(batch.pending)

    def filter(
        self,
        pairs: Sequence[Tuple[str, ...]],
        ready_starts: Iterable[str] = (),
        locked_starts: Iterable[str] = (),
    ) -> List[Tuple[str, ...]]:
        batch = self._scan.get()
        if not batch.active:
            if pairs:
                logger.debug(
                    "[gate] closed — drop %s pairs (batch inactive)",
                    len(pairs),
                )
            return []

        meta = self._start_meta()
        locked = list(locked_starts)
        plan = plan_col_dispatch(batch, meta, locked)

        # Báo cáo node mới ngoài batch — không halt
        ready_list = set(ready_starts)
        new_outside = ready_list - set(batch.nodes)
        if new_outside:
            logger.debug(
                "[gate] new_nodes_outside_batch nodes=%s hint=wait_next_confirm",
                sorted(new_outside),
            )

        if plan.skip_nodes:
            before = batch.remaining
            batch = self._scan.record_skip(plan.skip_nodes)
            logger.info(
                "[gate] col_skip nodes=%s remaining=%s→%s",
                sorted(plan.skip_nodes),
                before,
                batch.remaining,
            )
            emit(
                "system",
                "col_skipped",
                skippedNodes=sorted(plan.skip_nodes),
                remaining=batch.remaining,
                hint="Head col không trong batch — skip phần còn lại, sang col tiếp",
            )
            if should_auto_pause(batch):
                self._close_batch_complete()
                return []
            # Re-plan sau skip (có thể mở col tiếp trong cùng zone)
            plan = plan_col_dispatch(batch, meta, locked)

        allowed = [
            p for p in pairs if p[0] in plan.allow_starts
        ][: batch.remaining]

        if pairs and len(allowed) < len(pairs):
            logger.info(
                "[gate] pairs_filtered in=%s out=%s allow=%s busyZones=%s "
                "batchNodes=%s dispatched=%s skipped=%s remaining=%s locked=%s",
                len(pairs),
                len(allowed),
                sorted(plan.allow_starts),
                sorted(busy_zones(locked, meta)),
                sorted(batch.nodes),
                sorted(batch.dispatched),
                sorted(batch.skipped),
                batch.remaining,
                sorted(locked),
            )
        elif allowed:
            logger.debug(
                "[gate] allow %s pairs remaining=%s",
                len(allowed),
                batch.remaining,
            )
        return allowed

    def _close_batch_complete(self) -> None:
        batch = self._scan.get()
        dispatched = sorted(batch.dispatched)
        skipped = sorted(batch.skipped)
        size = batch.size
        self._scan.reset(reason=STOP_BATCH_COMPLETE)
        logger.info(
            "[gate] batch_complete after_skip size=%s dispatched=%s skipped=%s",
            size,
            dispatched,
            skipped,
        )
        emit(
            "system",
            "batch_complete",
            batchSize=size,
            dispatched=dispatched,
            skipped=skipped,
            hint="Đã gửi/skip hết batch — đẩy hàng đợt mới rồi dispatch",
        )
