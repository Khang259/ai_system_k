"""
Một vòng dispatch — ghép cặp + gửi qua DispatchGateway (payload ICS chung).
"""
from __future__ import annotations

from application.dispatch.ics_payload import build_single_payload
from application.result import UseCaseResult
from application.ports import DispatchGateway, NodeStateStore
from domain.dispatch.pairing import build_dispatch_pairs


class RunDispatchCycle:
    def __init__(self, state: NodeStateStore, gateway: DispatchGateway) -> None:
        self._state = state
        self._gateway = gateway

    def execute(self) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")

        self._state.process_starts()
        self._state.process_ends()

        pairs = build_dispatch_pairs(
            self._state.ready_starts(),
            self._state.ready_ends(),
            self._state.get_validate_pairs(),
        )

        sent = []
        failed = []
        for start_point, end_point in pairs:
            payload = build_single_payload(start_point, end_point)
            order_id = payload.get("orderId")
            ok = self._gateway.send(payload)
            if ok:
                self._state.set_pair_used(start_point, end_point, order_id)
                sent.append({"start": start_point, "end": end_point, "orderId": order_id})
            else:
                failed.append({"start": start_point, "end": end_point})

        return UseCaseResult.ok(sent=sent, failed=failed)
