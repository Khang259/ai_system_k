"""Xem trước dispatch — FE hiển thị trước khi người dùng confirm-dispatch."""
from __future__ import annotations

from typing import Callable

from application.ports import NodeStateStore
from application.result import UseCaseResult
from application.scan_session import ScanSession
from domain.batch_policy import (
    dispatchable_starts,
    locked_start_ids,
    plan_col_dispatch,
    stuck_nodes,
)
from domain.dispatch.pairing import build_dispatch_pairs
from domain.dispatch.priority import (
    StartMetaMap,
    col_of,
    resolve_priority,
    start_sort_key,
)
from utils.setup_log import setup_logger

logger = setup_logger("pending_pairs", "logs/pending_pairs/log")


class GetPendingPairs:
    def __init__(
        self,
        state: NodeStateStore,
        scan: ScanSession,
        start_meta: Callable[[], StartMetaMap],
    ) -> None:
        self._state = state
        self._scan = scan
        self._start_meta = start_meta

    def execute(self) -> UseCaseResult:
        batch_status = self._scan.status()
        empty = {
            "runtimeReady": False,
            "batch": batch_status,
            "readyStarts": [],
            "nextPairs": [],
            "waitingFor": [],
            "stuckNodes": [],
            "colStatus": [],
            "newNodesOutsideBatch": [],
        }
        if not self._state.is_ready():
            logger.debug("[pending_pairs] runtime not ready")
            return UseCaseResult.ok(**empty)

        meta = self._start_meta()
        validate_pairs = self._state.get_validate_pairs()
        ready = sorted(
            dispatchable_starts(self._state.ready_starts(), validate_pairs),
            key=lambda nid: start_sort_key(nid, meta),
        )
        batch = self._scan.get()
        locked = locked_start_ids(self._state.snapshot_points())
        ready_starts = [
            {
                "nodeId": nid,
                "priority": resolve_priority((meta.get(nid) or {}).get("priority")),
                "zoneId": (meta.get(nid) or {}).get("zone_id") or "",
                "colId": col_of(nid, meta),
                "inBatch": nid in batch.nodes,
                "dispatched": nid in batch.dispatched,
                "skipped": nid in batch.skipped,
            }
            for nid in ready
        ]

        # Trust: khi batch active, ghép từ pending batch
        starts_for_pairs = (
            sorted(batch.pending, key=lambda n: start_sort_key(n, meta))
            if batch.active
            else ready
        )
        built = build_dispatch_pairs(
            starts_for_pairs,
            self._state.ready_ends(),
            validate_pairs,
            start_meta=meta,
        )
        plan = (
            plan_col_dispatch(batch, meta, locked) if batch.active else None
        )
        pairs = built
        if plan is not None:
            pairs = [p for p in built if p[0] in plan.allow_starts][
                : batch.remaining
            ]

        next_pairs = [{"startNodeId": p[0], "endNodeId": p[1]} for p in pairs]
        waiting = list(plan.waiting) if plan else []
        stuck = stuck_nodes(batch, ready) if batch.active else []
        col_status = []
        if plan:
            for key, head in sorted(plan.col_heads.items()):
                zone, col = key.split("|", 1)
                col_status.append(
                    {
                        "zoneId": zone,
                        "colId": col,
                        "headNodeId": head,
                        "headInBatch": head in batch.nodes,
                    }
                )

        new_outside = sorted(set(ready) - set(batch.nodes)) if batch.active else []

        if batch.active and (waiting or stuck or (built and not pairs)):
            logger.debug(
                "[pending_pairs] batchActive ready=%s built=%s allowed=%s "
                "waitingFor=%s stuckNodes=%s locked=%s skipped=%s",
                ready,
                len(built),
                len(pairs),
                waiting,
                stuck,
                sorted(locked),
                sorted(batch.skipped),
            )

        return UseCaseResult.ok(
            runtimeReady=True,
            batch=batch_status,
            readyStarts=ready_starts,
            nextPairs=next_pairs,
            waitingFor=waiting,
            stuckNodes=stuck,
            colStatus=col_status,
            newNodesOutsideBatch=new_outside,
        )
