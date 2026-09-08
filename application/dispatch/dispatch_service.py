"""
Dispatch service — logic gửi ICS thuần, không thread/sleep (application layer).

PairManager (infrastructure) gọi service này trong loop.
Test gọi trực tiếp không cần mock thread.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from application.dispatch.ics_payload import (
    build_double_payload,
    build_empty_payload,
    build_single_payload,
)
from application.ports import DispatchGateway
from domain.dispatch.pairing import build_dispatch_pairs
from utils.setup_log import setup_logger

logger = setup_logger("dispatch_service", "logs/dispatch/log")

OnDispatchSuccessFn = Callable[[str], None]


class DispatchService:
    """
    Xử lý một vòng dispatch: ghép cặp từ ready lists + gửi ICS.
    
    Không biết thread/sleep. Infrastructure (PairManager) lo runtime loop.
    """

    def __init__(self, gateway: DispatchGateway) -> None:
        self._gateway = gateway

    def dispatch_single(
        self,
        pairs: List[Tuple[str, str]],
        state_manager,
        snapshot_manager=None,
        on_dispatch_success: Optional[OnDispatchSuccessFn] = None,
    ) -> Tuple[List, List]:
        """
        Single strategy: 1 start → 1 end.
        
        Returns: (sent_list, failed_list)
        """
        sent = []
        failed = []

        for start_point, end_point in pairs:
            # Chốt frame TRƯỚC khi gửi ICS (nếu có snapshot)
            capture = None
            if snapshot_manager:
                capture = snapshot_manager.capture_pair(start_point, end_point)
            
            payload = build_single_payload(start_point, end_point)
            order_id = payload.get("orderId")
            success = self._gateway.send(payload)
            
            logger.debug(
                f"[SINGLE] ({start_point} → {end_point}) orderId={order_id} success={success}"
            )

            if success:
                # Ghi file SAU khi ICS thành công
                if snapshot_manager:
                    snapshot_manager.save_pair_snapshots(
                        capture, start_point, end_point, order_id
                    )
                state_manager.set_pair_used(start_point, end_point, order_id, empty_car=False)
                if on_dispatch_success:
                    on_dispatch_success(start_point)
                sent.append({"start": start_point, "end": end_point, "orderId": order_id})
            else:
                logger.error(f"[SINGLE] Failed: ({start_point}, {end_point})")
                failed.append({"start": start_point, "end": end_point})

        return sent, failed

    def dispatch_empty(
        self,
        pending_empty_queue: list,
        end_point_empty: str,
        now: float,
        state_manager,
        snapshot_manager=None,
    ) -> Tuple[List, List]:
        """
        Empty strategy: start_empty → END_POINT_EMPTY cố định.
        Xử lý queue timeout.
        
        Returns: (sent_list, failed_list)
        """
        sent = []
        failed = []

        while pending_empty_queue:
            start_empty, deadline = pending_empty_queue[0]
            if now <= deadline:
                break

            payload = build_empty_payload(start_empty, end_point_empty)
            order_id = payload.get("orderId")
            success = self._gateway.send(payload)
            
            logger.debug(
                f"[EMPTY] ({start_empty} → {end_point_empty}) orderId={order_id} success={success}"
            )

            if success:
                # TODO: Implement capture_pair cho empty strategy khi bật
                # if snapshot_manager:
                #     snapshot_manager.save_pair_snapshots(...)
                state_manager.set_pair_used(start_empty, end_point_empty, order_id, empty_car=True)
                sent.append({"start": start_empty, "end": end_point_empty, "orderId": order_id})
            else:
                logger.error(f"[EMPTY] Failed: ({start_empty}, {end_point_empty})")
                failed.append({"start": start_empty, "end": end_point_empty})

            pending_empty_queue.pop(0)

        return sent, failed

    def dispatch_double(
        self,
        pairs: List[Tuple[str, str]],
        pending_empty_queue: list,
        end_point_empty: str,
        now: float,
        state_manager,
        snapshot_manager=None,
        on_dispatch_success: Optional[OnDispatchSuccessFn] = None,
    ) -> Tuple[List, List]:
        """
        Double strategy: ghép normal + empty → 1 lệnh double.
        Timeout empty → flush empty.
        
        Returns: (sent_list, failed_list)
        """
        sent = []
        failed = []
        normal_idx = 0

        while normal_idx < len(pairs) and pending_empty_queue:
            start_empty, deadline = pending_empty_queue[0]

            if now > deadline:
                # Flush empty timeout
                payload = build_empty_payload(start_empty, end_point_empty)
                order_id = payload.get("orderId")
                success = self._gateway.send(payload)
                logger.debug(f"[DOUBLE→EMPTY flush] ({start_empty}) orderId={order_id}")
                
                if success:
                    # TODO: Implement capture_pair cho empty flush khi bật
                    # if snapshot_manager:
                    #     snapshot_manager.save_pair_snapshots(...)
                    state_manager.set_pair_used(start_empty, end_point_empty, order_id, empty_car=True)
                    sent.append({"start": start_empty, "end": end_point_empty, "orderId": order_id})
                else:
                    logger.error(f"[DOUBLE] Empty flush failed: {start_empty}")
                    failed.append({"start": start_empty, "end": end_point_empty})
                
                pending_empty_queue.pop(0)
                continue

            # Double dispatch
            start_point, end_point = pairs[normal_idx]
            payload = build_double_payload(start_point, end_point, start_empty, end_point_empty)
            order_id = payload.get("orderId")
            success = self._gateway.send(payload)
            
            logger.debug(
                f"[DOUBLE] ({start_point},{end_point})+({start_empty},{end_point_empty}) orderId={order_id}"
            )

            if success:
                # TODO: Implement capture_pair cho double strategy khi bật
                # if snapshot_manager:
                #     snapshot_manager.save_pair_snapshots(...)
                state_manager.set_pair_used(start_point, end_point, order_id, empty_car=False)
                state_manager.set_pair_used(start_empty, end_point_empty, order_id, empty_car=True)
                if on_dispatch_success:
                    on_dispatch_success(start_point)
                sent.append({
                    "start": start_point,
                    "end": end_point,
                    "start_empty": start_empty,
                    "orderId": order_id
                })
            else:
                logger.error(
                    f"[DOUBLE] Failed: ({start_point},{end_point})+({start_empty},{end_point_empty})"
                )
                failed.append({
                    "start": start_point,
                    "end": end_point,
                    "start_empty": start_empty
                })

            pending_empty_queue.pop(0)
            normal_idx += 1

        # Remaining normal pairs → single
        for pair in pairs[normal_idx:]:
            start_point, end_point = pair
            payload = build_single_payload(start_point, end_point)
            order_id = payload.get("orderId")
            success = self._gateway.send(payload)
            logger.debug(f"[DOUBLE→SINGLE overflow] ({start_point},{end_point})")
            
            if success:
                # TODO: Implement capture_pair cho overflow single khi bật
                # if snapshot_manager:
                #     snapshot_manager.save_pair_snapshots(...)
                state_manager.set_pair_used(start_point, end_point, order_id, empty_car=False)
                if on_dispatch_success:
                    on_dispatch_success(start_point)
                sent.append({"start": start_point, "end": end_point, "orderId": order_id})
            else:
                logger.error(f"[DOUBLE→SINGLE] Failed: ({start_point}, {end_point})")
                failed.append({"start": start_point, "end": end_point})

        return sent, failed

    def build_pairs(
        self,
        state_manager,
    ) -> List[Tuple[str, str]]:
        """Helper: ghép cặp từ state manager."""
        return build_dispatch_pairs(
            state_manager.ready_starts(),
            state_manager.ready_ends(),
            state_manager.get_validate_pairs(),
        )
