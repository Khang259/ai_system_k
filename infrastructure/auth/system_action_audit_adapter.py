"""Adapter ghi dispatch_logs — webhook ICS vào BE + outbound ICS từ PairManager."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from config.settings import settings
from infrastructure.persistence.base_repository import _now
from infrastructure.persistence.dispatch_log_repository import dispatch_log_repository
from utils.setup_log import setup_logger

logger = setup_logger("system_action_audit", "logs/dispatch/log")


class SystemActionAuditAdapter:
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def log(
        self,
        *,
        action: str,
        order_id: Optional[str],
        endpoint: str,
        payload: Dict[str, Any],
        status: int,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        start_point: Optional[str] = None,
        end_point: Optional[str] = None,
    ) -> None:
        ok = 200 <= int(status) < 300
        await dispatch_log_repository.create(
            {
                "order_id": order_id,
                "action": action,
                "status": "success" if ok else "failed",
                "error_msg": error,
                "dispatched_at": _now(),
                "endpoint": endpoint,
                "request_payload": payload or {},
                "response_payload": result or {},
                "external_source": "ICS",
                "start_point": start_point,
                "end_point": end_point,
            }
        )

    def log_outbound(
        self,
        *,
        action: str = "dispatch",
        order_id: Optional[str],
        payload: Dict[str, Any],
        success: bool,
        start_point: Optional[str] = None,
        end_point: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Fire-and-forget từ thread PairManager → dispatch_logs."""
        coro = self.log(
            action=action,
            order_id=order_id,
            endpoint=settings.ICS_URL,
            payload=payload or {},
            status=200 if success else 502,
            result={"ok": True} if success else None,
            error=None if success else (error or "ICS request failed"),
            start_point=start_point,
            end_point=end_point,
        )
        loop = self._loop
        if loop is None or not loop.is_running():
            logger.warning("Bỏ qua dispatch_logs outbound: event loop chưa sẵn sàng")
            return

        def _done(fut: asyncio.Future) -> None:
            try:
                fut.result()
            except Exception:
                logger.exception("Ghi dispatch_logs outbound thất bại")

        try:
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
            fut.add_done_callback(_done)
        except Exception:
            logger.exception("Không schedule được dispatch_logs outbound")
