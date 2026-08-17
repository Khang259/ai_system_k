from domain.batch_policy import find_new_nodes, should_auto_pause
from application.ports import InferencePort, NodeStateStore
from application.scan_session import ScanSession


class OnDispatchSuccess:
    """Internal — PairManager gọi sau mỗi dispatch thành công."""

    def __init__(
        self,
        inference: InferencePort,
        state: NodeStateStore,
        scan: ScanSession,
    ) -> None:
        self._inference = inference
        self._state = state
        self._scan = scan

    def execute(self, node_id: str) -> None:
        batch = self._scan.get()
        if not batch.active:
            return

        batch = self._scan.record_success()
        if should_auto_pause(batch):
            if self._inference.is_ready():
                self._inference.pause()
            self._scan.reset()
            return

        if not self._state.is_ready():
            return
        new_nodes = find_new_nodes(
            self._state.get_detected_start_nodes(),
            batch.nodes,
        )
        if new_nodes:
            if self._inference.is_ready():
                self._inference.pause()
            self._scan.reset()
