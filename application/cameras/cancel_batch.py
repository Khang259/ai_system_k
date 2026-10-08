from application.result import UseCaseResult
from application.scan_session import STOP_CANCELED, ScanSession
from infrastructure.sandbox.smoke_trail import emit


class CancelBatch:
    """Huỷ batch đang mở — đóng cổng gửi. Inference vẫn chạy."""

    def __init__(self, scan: ScanSession) -> None:
        self._scan = scan

    def execute(self) -> UseCaseResult:
        batch = self._scan.get()
        if not batch.active:
            return UseCaseResult.fail(
                "Không có batch đang chạy",
                http_status=409,
            )
        remaining = sorted(batch.nodes - batch.dispatched)
        self._scan.reset(reason=STOP_CANCELED)
        emit(
            "api",
            "cancel_batch",
            dispatched=sorted(batch.dispatched),
            remaining=remaining,
            hint="Batch huỷ — inference vẫn chạy; confirm-dispatch khi sẵn sàng",
        )
        return UseCaseResult.ok(
            message="Batch canceled",
            dispatched=sorted(batch.dispatched),
            remaining=remaining,
        )
