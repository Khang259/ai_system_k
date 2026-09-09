"""User repository — collection: users. Implements UserRepositoryPort."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from infrastructure.persistence.base_repository import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users")

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return await self.find_one({"username": username.lower().strip()})

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.find_one({"user_id": user_id})

    async def get_all(self) -> List[Dict[str, Any]]:
        return await self.find_many({})

    async def create(self, doc: Dict[str, Any]) -> str:
        return await self.insert_one(doc)

    async def set_enabled(self, user_id: str, enabled: bool) -> bool:
        return await self.update_one({"user_id": user_id}, {"enabled": enabled})

    async def set_password(self, user_id: str, password_hash: str) -> bool:
        return await self.update_one(
            {"user_id": user_id}, {"password_hash": password_hash}
        )


user_repository = UserRepository()
