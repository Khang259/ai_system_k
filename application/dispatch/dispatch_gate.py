"""
Cổng gửi ICS — PairManager gọi mỗi vòng trước khi dispatch.

Đóng khi chưa confirm-dispatch / batch xong / có start mới ngoài batch.
Inference không bị pause bởi cổng — chỉ việc gửi lệnh bị chặn.

Strict order theo zone: chỉ gửi head của mỗi zone; zone đang có lệnh thì chờ.
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from application.scan_session import STOP_NEW_NODES, ScanSession
from domain.batch_policy import allowed_pairs, find_new_nodes
from domain.dispatch.priority import StartMetaMap
from infrastructure.sandbox.smoke_trail import emit


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
            return []

        new_nodes = find_new_nodes(ready_starts, batch.nodes)
        if new_nodes:
            self._scan.reset(reason=STOP_NEW_NODES, new_nodes=new_nodes)
            emit(
                "system",
                "batch_halted",
                reason=STOP_NEW_NODES,
                newNodes=sorted(new_nodes),
                dispatched=sorted(batch.dispatched),
                hint="Có start isReady ngoài batch — kiểm tra hiện trường rồi confirm-dispatch lại",
            )
            return []

        return allowed_pairs(
            batch,
            pairs,
            start_meta=self._start_meta(),
            locked_starts=locked_starts,
        )
