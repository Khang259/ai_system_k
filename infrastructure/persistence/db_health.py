"""Mongo ping adapter cho /health."""
from __future__ import annotations

from infrastructure.persistence.db import get_db


class MongoHealthAdapter:
    async def ping(self) -> bool:
        try:
            await get_db().command("ping")
            return True
        except Exception:
            return False
