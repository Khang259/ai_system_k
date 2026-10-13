"""
Cổng gửi ICS — PairManager gọi mỗi vòng trước khi dispatch.

Đóng khi chưa confirm-dispatch / batch xong / có start mới ngoài batch.
Inference không bị pause bởi cổng — chỉ việc gửi lệnh bị chặn.

Strict order theo zone: chỉ gửi head của mỗi zone; zone đang có lệnh thì chờ.
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from application.scan_session import STOP_NEW_NODES, ScanSession
from domain.batch_policy import allowed_pairs, busy_zones, find_new_nodes, zone_heads
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

    def filter(
        self,
        pairs: Sequence[Tuple[str, ...]],
        ready_starts: Iterable[str],
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

        ready_list = list(ready_starts)
        new_nodes = find_new_nodes(ready_list, batch.nodes)
        if new_nodes:
            self._scan.reset(reason=STOP_NEW_NODES, new_nodes=new_nodes)
            sorted_new = sorted(new_nodes)
            sorted_dispatched = sorted(batch.dispatched)
            logger.info(
                "[gate] batch_halted reason=%s newNodes=%s dispatched=%s",
                STOP_NEW_NODES,
                sorted_new,
                sorted_dispatched,
            )
            emit(
                "system",
                "batch_halted",
                reason=STOP_NEW_NODES,
                newNodes=sorted_new,
                dispatched=sorted_dispatched,
                hint="Có start isReady ngoài batch — kiểm tra hiện trường rồi confirm-dispatch lại",
            )
            return []

        meta = self._start_meta()
        locked = list(locked_starts)
        allowed = allowed_pairs(
            batch,
            pairs,
            start_meta=meta,
            locked_starts=locked,
        )
        if pairs and len(allowed) < len(pairs):
            logger.info(
                "[gate] pairs_filtered in=%s out=%s heads=%s busyZones=%s "
                "batchNodes=%s dispatched=%s remaining=%s locked=%s",
                len(pairs),
                len(allowed),
                zone_heads(batch, meta),
                sorted(busy_zones(locked, meta)),
                sorted(batch.nodes),
                sorted(batch.dispatched),
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
