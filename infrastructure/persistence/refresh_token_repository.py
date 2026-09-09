"""
Refresh token repository — collection: refresh_tokens.

Single session (chốt 2026-09-09): mỗi user tối đa **một** phiên. Đăng nhập máy
mới đẩy máy cũ ra. Chỉ lưu hash, không lưu token thô.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.persistence.base_repository import BaseRepository, _now


class RefreshTokenRepository(BaseRepository):
    def __init__(self):
        super().__init__("refresh_tokens")

    async def save(
        self, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        """
        Ghi đè phiên của user — `replace_one(upsert=True)` chứ không phải
        delete rồi insert, để hai lần đăng nhập sát nhau không tạo ra hai bản
        ghi (thao tác này là nguyên tử ở phía Mongo).
        """
        await self._col().replace_one(
            {"user_id": user_id},
            {
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "created_at": _now(),
            },
            upsert=True,
        )

    async def find(self, token_hash: str) -> Optional[Dict[str, Any]]:
        return await self.find_one({"token_hash": token_hash})

    async def revoke_user(self, user_id: str) -> None:
        await self._col().delete_many({"user_id": user_id})


refresh_token_repository = RefreshTokenRepository()
