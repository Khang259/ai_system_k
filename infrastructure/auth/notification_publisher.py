"""
Publisher thông báo — gọi được từ thread PairManager (sync).

Ghi Mongo qua motor bằng run_coroutine_threadsafe vào event loop FastAPI.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from utils.setup_log import setup_logger

logger = setup_logger("notification_publisher", "logs/notification_publisher/log")


class NotificationPublisher:
    def __init__(self, repo) -> None:
        self._repo = repo
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish_dispatch_failed(
        self,
        start_node_id: str,
        end_node_id: str,
        order_id: Optional[str] = None,
        error: str = "",
    ) -> None:
        """Fire-and-forget từ thread sync. Không ném ra caller dispatch."""
        title = "Lệnh thất bại"
        end_s = end_node_id or "?"
        message = f"ICS thất bại: {start_node_id} → {end_s}"
        if error:
            message = f"{message} ({error})"
        meta: dict[str, Any] = {
            "startNodeId": start_node_id,
            "endNodeId": end_node_id,
            "orderId": order_id,
        }
        coro = self._repo.create(
            title=title,
            message=message,
            type="dispatch.failed",
            user_id=None,
            meta=meta,
            snapshot_file=None,
        )
        loop = self._loop
        if loop is None or not loop.is_running():
            logger.warning("Bỏ qua notification: event loop chưa sẵn sàng")
            return

        def _done(fut: asyncio.Future) -> None:
            try:
                fut.result()
            except Exception:
                logger.exception("Ghi notification dispatch.failed thất bại")

        try:
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
            fut.add_done_callback(_done)
        except Exception:
            logger.exception("Không schedule được notification")


class NullNotificationPublisher:
    def bind_loop(self, loop) -> None:
        return None

    def publish_dispatch_failed(
        self, start_node_id, end_node_id, order_id=None, error=""
    ) -> None:
        return None
