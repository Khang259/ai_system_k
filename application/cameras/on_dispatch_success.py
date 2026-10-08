from domain.batch_policy import should_auto_pause
from application.scan_session import STOP_BATCH_COMPLETE, ScanSession
from infrastructure.sandbox.smoke_trail import emit


class OnDispatchSuccess:
    """Internal — PairManager gọi sau mỗi dispatch thành công."""

    def __init__(self, scan: ScanSession) -> None:
        self._scan = scan

    def execute(self, node_id: str) -> None:
        if not self._scan.get().active:
            return

        batch = self._scan.record_success(node_id)
        if should_auto_pause(batch):
            # Đóng cổng gửi; inference vẫn chạy để FE thấy hàng đợt mới
            self._scan.reset(reason=STOP_BATCH_COMPLETE)
            emit(
                "system",
                "batch_complete",
                lastStartNodeId=node_id,
                batchSize=batch.size,
                dispatched=sorted(batch.dispatched),
                hint="Đã gửi hết batch — đẩy hàng đợt mới rồi confirm-dispatch",
            )
