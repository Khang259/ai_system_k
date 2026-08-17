"""
Shared MongoDB connection — dùng chung cho tất cả repositories.
Chỉ có 1 client duy nhất trong toàn bộ app.
"""
from __future__ import annotations

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from utils.setup_log import setup_logger

logger = setup_logger("database", "logs/database/log")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect(url: str, db_name: str) -> None:
    global _client, _db
    _client = AsyncIOMotorClient(url)
    _db     = _client[db_name]
    logger.info(f"MongoDB connected: {db_name}")


async def disconnect() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db     = None
        logger.info("MongoDB disconnected")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not connected. Call connect() first.")
    return _db


def get_collection(name: str):
    return get_db()[name]
