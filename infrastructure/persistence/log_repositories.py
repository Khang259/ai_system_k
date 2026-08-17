"""
Action log repository — collection: action_logs
Audit log repository — collection: audit_logs
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from infrastructure.persistence.base_repository import BaseRepository


class ActionLogRepository(BaseRepository):
    def __init__(self):
        super().__init__("action_logs")

    async def log(
        self,
        user: str,
        role: str,
        action: str,
        endpoint: str,
        payload: Dict,
        ip: str,
        status: int,
        source: str = "user",
    ) -> str:
        return await self.insert_one({
            "user": user,
            "role": role,
            "action": action,
            "endpoint": endpoint,
            "payload": payload,
            "ip": ip,
            "status": status,
            "source": source,
        })

    async def get_by_user(self, user: str, days: int = 7) -> List[Dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.find_many(
            {"user": user, "created_at": {"$gte": since}},
            sort=[("created_at", -1)],
        )

    async def get_recent(self, limit: int = 100) -> List[Dict]:
        return await self.find_many({}, sort=[("created_at", -1)], limit=limit)


class AuditLogRepository(BaseRepository):
    def __init__(self):
        super().__init__("audit_logs")

    async def log(
        self,
        user: str,
        role: str,
        event: str,
        ip: str,
        user_agent: str = "",
    ) -> str:
        return await self.insert_one({
            "user": user,
            "role": role,
            "event": event,
            "ip": ip,
            "user_agent": user_agent,
        })

    async def get_by_user(self, user: str, limit: int = 50) -> List[Dict]:
        return await self.find_many(
            {"user": user},
            sort=[("created_at", -1)],
            limit=limit,
        )

    async def get_failed_logins(self, since_minutes: int = 30) -> List[Dict]:
        since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        return await self.find_many(
            {"event": "login_failed", "created_at": {"$gte": since}},
            sort=[("created_at", -1)],
        )

    async def get_all(self, limit: int = 200) -> List[Dict]:
        return await self.find_many({}, sort=[("created_at", -1)], limit=limit)


action_log_repository = ActionLogRepository()
audit_log_repository = AuditLogRepository()
