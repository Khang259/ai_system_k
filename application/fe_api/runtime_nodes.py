"""Runtime node state — snapshot RAM cho FE (detected / isReady / lock)."""
from __future__ import annotations

from typing import Any, Dict, List

from application.ports import NodeStateStore
from application.result import UseCaseResult
from application.runtime.runtime_state_hub import map_runtime_item


class GetNodeRuntimeState:
    """
    Snapshot vận hành từ RAM.

    runtimeReady=false + items=[] khi state manager chưa sẵn (không 500).
    """

    def __init__(self, state: NodeStateStore) -> None:
        self._state = state

    def execute(self) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.ok(runtimeReady=False, items=[])
        snap = self._state.snapshot_points() or {}
        items: List[Dict[str, Any]] = [
            map_runtime_item(nid, data) for nid, data in snap.items()
        ]
        items.sort(key=lambda r: r.get("nodeId") or "")
        return UseCaseResult.ok(runtimeReady=True, items=items)
