from typing import Callable

from application.result import UseCaseResult
from application.ports import InferencePort, NodeStateStore
from application.scan_session import ScanSession
from domain.batch_policy import dispatchable_starts
from domain.dispatch.priority import StartMetaMap, start_sort_key
from infrastructure.sandbox.smoke_trail import emit
from utils.setup_log import setup_logger

logger = setup_logger("confirm_dispatch", "logs/confirm_dispatch/log")


class ConfirmDispatch:
    """
    Người dùng xác nhận hàng đã đẩy xong → chụp batch các start isReady và mở cổng
    gửi ICS. Chỉ start trong batch được gửi, theo priority, mỗi start 1 lần.
    """

    def __init__(
        self,
        inference: InferencePort,
        state: NodeStateStore,
        scan: ScanSession,
        start_meta: Callable[[], StartMetaMap],
    ) -> None:
        self._inference = inference
        self._state = state
        self._scan = scan
        self._start_meta = start_meta

    def execute(self) -> UseCaseResult:
        if not self._inference.is_ready() or not self._state.is_ready():
            logger.warning("[confirm_dispatch] reject reason=not_initialized")
            return UseCaseResult.fail("System not initialized")
        if self._inference.is_paused():
            logger.warning(
                "[confirm_dispatch] reject reason=inference_paused "
                "hint=POST /api/v1/runtime/start-scan"
            )
            return UseCaseResult.fail(
                "Inference đang pause — gọi POST /api/v1/runtime/start-scan trước",
                http_status=409,
            )
        if self._scan.get().active:
            batch = self._scan.get()
            logger.warning(
                "[confirm_dispatch] reject reason=batch_active "
                "batchNodes=%s dispatched=%s remaining=%s",
                sorted(batch.nodes),
                sorted(batch.dispatched),
                batch.remaining,
            )
            return UseCaseResult.fail(
                "Batch trước chưa xong — chờ gửi hết hoặc cancel-batch / pause-scan để huỷ",
                http_status=409,
            )

        raw_ready = self._state.ready_starts()
        ready = dispatchable_starts(raw_ready, self._state.get_validate_pairs())
        if not ready:
            logger.warning(
                "[confirm_dispatch] reject reason=no_dispatchable_starts "
                "readyStarts=%s",
                sorted(raw_ready),
            )
            return UseCaseResult.fail(
                "Chưa có start isReady — chờ hàng được nhận diện ổn định",
                http_status=409,
            )

        batch = self._scan.start(ready)
        meta = self._start_meta()
        ordered = sorted(batch.nodes, key=lambda nid: start_sort_key(nid, meta))
        logger.info(
            "[confirm_dispatch] ok batchSize=%s batchNodes=%s",
            batch.size,
            ordered,
        )
        emit("api", "confirm_dispatch", batchSize=batch.size, batchNodes=ordered)
        return UseCaseResult.ok(
            message="Dispatch confirmed",
            batchSize=batch.size,
            batchNodes=ordered,
        )
