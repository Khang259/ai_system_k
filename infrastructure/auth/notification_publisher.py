"""
Publisher thông báo — gọi được từ thread PairManager (sync).

Ghi Mongo qua motor bằng run_coroutine_threadsafe vào event loop FastAPI.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from utils.setup_log import setup_logger

logger = setup_logger("notification_publisher", "logs/notification_publisher/log")


class NotificationPublisher:
    def __init__(self, repo) -> None:
        self._repo = repo
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop


class NullNotificationPublisher:
    def bind_loop(self, loop) -> None:
        return None
