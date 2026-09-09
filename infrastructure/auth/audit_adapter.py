"""
Nối sự kiện đăng nhập vào `audit_logs` — implement AuthAuditPort.

Dùng lại `audit_log_repository` đã có sẵn trong repo (trước đây chưa ai gọi).
"""
from __future__ import annotations

from infrastructure.persistence.log_repositories import audit_log_repository


class AuthAuditAdapter:
    async def log_event(
        self, username: str, event: str, ip: str, user_agent: str = ""
    ) -> None:
        await audit_log_repository.log(
            user=username,
            role="",
            event=event,
            ip=ip,
            user_agent=user_agent,
        )

    async def count_recent_failures(self, username: str, minutes: int) -> int:
        return await audit_log_repository.count_failed_logins_for(username, minutes)
