"""Adapter ghi action_logs — thao tác người dùng qua /api/v1."""
from __future__ import annotations

from typing import Any, Dict

from infrastructure.persistence.log_repositories import action_log_repository

_SENSITIVE_KEYS = {"password", "token", "accesstoken", "refreshtoken", "authorization"}


def _redact(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (payload or {}).items():
        key_l = k.lower()
        if key_l in _SENSITIVE_KEYS or "password" in key_l or "token" in key_l:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out


class ActionAuditAdapter:
    async def log(
        self,
        user: str,
        role: str,
        action: str,
        endpoint: str,
        payload: Dict[str, Any],
        ip: str,
        status: int,
    ) -> None:
        await action_log_repository.log(
            user=user,
            role=role,
            action=action,
            endpoint=endpoint,
            payload=_redact(payload),
            ip=ip,
            status=status,
            source="user",
        )
