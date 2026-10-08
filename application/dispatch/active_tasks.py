"""
Use cases panel order đang chạy:
- TrackDispatchedTask: gửi ICS OK → order "issued"
- GetActiveTasks: sau restart, nạp lại từ ICS getOrderList
- UnlockByOrderStatus: webhook ICS (6 → inprogress, 3|23 → gỡ lock + xóa)
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Protocol

from application.dispatch.active_task_hub import ActiveTaskHub
from application.ports import IcsOrderQueryPort, NodeRepositoryPort
from application.result import UseCaseResult
from domain.dispatch.active_task import build_active_task, sort_active_tasks, status_label
from domain.dispatch.priority import StartMetaMap, start_meta_from_docs
from domain.models import OrderStatus


class _ResetFlags(Protocol):
    def execute(self, order_id: str, status: int) -> UseCaseResult: ...


class StartPriorityReader:
    """Priority start: map runtime nạp lúc start; runtime chưa start → đọc Mongo."""

    def __init__(
        self,
        nodes_repo: NodeRepositoryPort,
        runtime_meta: Callable[[], StartMetaMap],
    ) -> None:
        self._nodes = nodes_repo
        self._runtime_meta = runtime_meta

    async def read(self) -> StartMetaMap:
        meta = self._runtime_meta()
        if meta:
            return meta
        return start_meta_from_docs(await self._nodes.get_all())


class TrackDispatchedTask:
    """Gọi từ thread PairManager ngay sau khi ICS nhận lệnh."""

    def __init__(self, hub: ActiveTaskHub, runtime_meta: Callable[[], StartMetaMap]) -> None:
        self._hub = hub
        self._runtime_meta = runtime_meta

    def execute(self, order_id: str) -> None:
        item = build_active_task(
            order_id, status_label(OrderStatus.ASSIGNED), self._runtime_meta()
        )
        if item:
            self._hub.upsert(item)


class GetActiveTasks:
    def __init__(
        self,
        order_query: IcsOrderQueryPort,
        hub: ActiveTaskHub,
        priorities: StartPriorityReader,
        area_id: int,
    ) -> None:
        self._query = order_query
        self._hub = hub
        self._priorities = priorities
        self._area_id = area_id

    async def execute(self) -> UseCaseResult:
        try:
            tasks = await asyncio.to_thread(self._query.get_order_list, self._area_id)
        except Exception as e:
            return UseCaseResult.fail(
                f"Không lấy được danh sách lệnh từ ICS: {e}", http_status=502
            )

        start_meta = await self._priorities.read()
        items: Dict[str, Dict[str, Any]] = {}
        for task in tasks:
            label = status_label(task.get("OrderStatus"))
            if label is None:
                continue
            item = build_active_task(task.get("OrderId"), label, start_meta)
            if item:
                items[item["orderId"]] = item

        sorted_items = sort_active_tasks(items.values())
        self._hub.replace_all(sorted_items)
        return UseCaseResult.ok(items=sorted_items)


class UnlockByOrderStatus:
    def __init__(
        self,
        reset_flags: _ResetFlags,
        hub: ActiveTaskHub,
        priorities: StartPriorityReader,
    ) -> None:
        self._reset = reset_flags
        self._hub = hub
        self._priorities = priorities

    async def execute(self, order_id: str, status: int) -> UseCaseResult:
        if OrderStatus.clears_order(status):
            # Canceled (3) / Placed (23) → luôn xóa khỏi panel, kể cả khi reset lock lỗi
            self._hub.remove(order_id)
            return self._reset.execute(order_id, status)

        label = status_label(status)
        if label is None:
            return UseCaseResult.ok(
                message=f"Bỏ qua status {status}", orderId=order_id
            )

        if not self._hub.set_status(order_id, label):
            # Panel chưa có (vd. vừa restart app) → tự thêm từ orderId
            item = build_active_task(order_id, label, await self._priorities.read())
            if item:
                self._hub.upsert(item)
        return UseCaseResult.ok(
            message=f"orderId {order_id} → {label}", orderId=order_id, status=label
        )
