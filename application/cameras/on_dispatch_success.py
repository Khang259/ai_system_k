from domain.batch_policy import should_auto_pause
from application.scan_session import STOP_BATCH_COMPLETE, ScanSession
from infrastructure.sandbox.smoke_trail import emit
from utils.setup_log import setup_logger

logger = setup_logger("on_dispatch_success", "logs/on_dispatch_success/log")


class OnDispatchSuccess:
    """Internal — PairManager gọi sau mỗi dispatch thành công."""

    def __init__(self, scan: ScanSession) -> None:
        self._scan = scan

    def execute(self, node_id: str) -> None:
        if not self._scan.get().active:
            logger.debug(
                "[on_dispatch_success] ignore node=%s reason=batch_inactive",
                node_id,
            )
            return

        batch = self._scan.record_success(node_id)
        logger.info(
            "[on_dispatch_success] recorded node=%s sum_request=%s remaining=%s "
            "dispatched=%s",
            node_id,
            batch.sum_request,
            batch.remaining,
            sorted(batch.dispatched),
        )
        if should_auto_pause(batch):
            # Đóng cổng gửi; inference vẫn chạy để FE thấy hàng đợt mới
            dispatched = sorted(batch.dispatched)
            self._scan.reset(reason=STOP_BATCH_COMPLETE)
            logger.info(
                "[on_dispatch_success] batch_complete lastStart=%s batchSize=%s "
                "dispatched=%s",
                node_id,
                batch.size,
                dispatched,
            )
            emit(
                "system",
                "batch_complete",
                lastStartNodeId=node_id,
                batchSize=batch.size,
                dispatched=dispatched,
                hint="Đã gửi hết batch — đẩy hàng đợt mới rồi confirm-dispatch",
            )
