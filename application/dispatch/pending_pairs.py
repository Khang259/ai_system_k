"""Xem trước dispatch — FE hiển thị trước khi người dùng confirm-dispatch."""
from __future__ import annotations

from typing import Callable

from application.ports import NodeStateStore
from application.result import UseCaseResult
from application.scan_session import ScanSession
from domain.batch_policy import (
    allowed_pairs,
    dispatchable_starts,
    locked_start_ids,
    stuck_nodes,
    waiting_for,
)
from domain.dispatch.pairing import build_dispatch_pairs
from domain.dispatch.priority import StartMetaMap, resolve_priority, start_sort_key


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
        }
        if not self._state.is_ready():
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
                "inBatch": nid in batch.nodes,
                "dispatched": nid in batch.dispatched,
            }
            for nid in ready
        ]

        pairs = build_dispatch_pairs(
            ready,
            self._state.ready_ends(),
            validate_pairs,
            start_meta=meta,
        )
        if batch.active:
            pairs = allowed_pairs(
                batch, pairs, start_meta=meta, locked_starts=locked
            )
        next_pairs = [{"startNodeId": p[0], "endNodeId": p[1]} for p in pairs]

        return UseCaseResult.ok(
            runtimeReady=True,
            batch=batch_status,
            readyStarts=ready_starts,
            nextPairs=next_pairs,
            waitingFor=waiting_for(batch, meta, ready, locked),
            stuckNodes=stuck_nodes(batch, ready),
        )
