"""
Ghi metadata snapshot vào Mongo — gọi từ thread PairManager (sync).

Ảnh vẫn nằm trên đĩa; Mongo chỉ là chỉ mục theo orderId / nodeId.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

from utils.setup_log import setup_logger

logger = setup_logger("snapshot_indexer", "logs/snapshot_fs/log")


class SnapshotIndexer:
    def __init__(self, repo) -> None:
        self._repo = repo
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def record(
        self,
        *,
        order_id: str,
        node_id: str,
        node_type: str,
        zone_id: str,
        image_path: str,
        decision: str = "auto",
    ) -> None:
        """Fire-and-forget. `image_path` = basename file JPEG (cho get_image)."""
        filename = os.path.basename(image_path) if image_path else ""
        if not filename or not order_id or not node_id:
            return

        coro = self._repo.create(
            order_id=order_id,
            node_id=node_id,
            node_type=node_type,
            zone_id=zone_id or "",
            decision=decision,
            image_path=filename,
        )
        loop = self._loop
        if loop is None or not loop.is_running():
            logger.warning("Bỏ qua snapshot Mongo: event loop chưa sẵn sàng")
            return

        def _done(fut: asyncio.Future) -> None:
            try:
                fut.result()
            except Exception:
                logger.exception(
                    "Ghi snapshot Mongo thất bại orderId=%s node=%s",
                    order_id,
                    node_id,
                )

        try:
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
            fut.add_done_callback(_done)
        except Exception:
            logger.exception("Không schedule được snapshot Mongo")


class NullSnapshotIndexer:
    def bind_loop(self, loop) -> None:
        return None

    def record(self, **kwargs) -> None:
        return None
