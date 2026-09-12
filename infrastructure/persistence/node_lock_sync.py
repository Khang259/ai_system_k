"""
Persist field Mongo `lock` trên node — gọi được từ thread PairManager (sync).

Một field duy nhất:
  lock: { "user": bool, "system": bool, "orderId": str|null }
"""
from __future__ import annotations

import asyncio
from typing import Iterable, Optional

from utils.setup_log import setup_logger

logger = setup_logger("node_lock_sync", "logs/dispatch/log")


class NodeLockSync:
    def __init__(self, repo) -> None:
        self._repo = repo
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _schedule(self, coro) -> None:
        loop = self._loop
        if loop is None or not loop.is_running():
            logger.warning("Bỏ qua ghi lock Mongo: event loop chưa sẵn sàng")
            return

        def _done(fut: asyncio.Future) -> None:
            try:
                fut.result()
            except Exception:
                logger.exception("Ghi lock Mongo thất bại")

        try:
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
            fut.add_done_callback(_done)
        except Exception:
            logger.exception("Không schedule được ghi lock")

    def set_user(self, node_id: str, enabled: bool) -> None:
        self._schedule(self._repo.set_lock(node_id, user=enabled))

    def set_system_pair(self, start_id: str, end_id: str, order_id: str) -> None:
        async def _both():
            await self._repo.set_lock(
                start_id, system=True, order_id=order_id
            )
            await self._repo.set_lock(end_id, system=True, order_id=order_id)

        self._schedule(_both())

    def clear_system(self, node_ids: Iterable[str]) -> None:
        ids = [n for n in node_ids if n]

        async def _clear():
            for nid in ids:
                await self._repo.set_lock(nid, system=False)

        if ids:
            self._schedule(_clear())

    def clear_system_by_order(self, order_id: str) -> None:
        self._schedule(self._repo.clear_system_lock_by_order(order_id))


class NullNodeLockSync:
    def bind_loop(self, loop) -> None:
        return None

    def set_user(self, node_id: str, enabled: bool) -> None:
        return None

    def set_system_pair(self, start_id: str, end_id: str, order_id: str) -> None:
        return None

    def clear_system(self, node_ids) -> None:
        return None

    def clear_system_by_order(self, order_id: str) -> None:
        return None
