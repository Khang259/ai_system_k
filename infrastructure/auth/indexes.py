"""
Index cho collection auth — gọi một lần lúc khởi động.

`create_index` là idempotent nên gọi lại nhiều lần không sao.
"""
from __future__ import annotations

from infrastructure.persistence.db import get_collection
from utils.setup_log import setup_logger

logger = setup_logger("auth", "logs/auth/log")


async def ensure_auth_indexes() -> None:
    try:
        users = get_collection("users")
        await users.create_index("username", unique=True)
        await users.create_index("user_id", unique=True)

        tokens = get_collection("refresh_tokens")
        await tokens.create_index("token_hash", unique=True)
        # unique theo user_id = single session được đảm bảo ở tầng DB, không
        # chỉ dựa vào replace_one trong repository
        await tokens.create_index("user_id", unique=True)
        # TTL: Mongo tự xoá token hết hạn, không cần scheduler dọn
        await tokens.create_index("expires_at", expireAfterSeconds=0)

        logger.info("Auth indexes ensured")
    except Exception as e:
        # Không chặn khởi động: index thiếu làm hiệu năng kém và mất ràng buộc,
        # nhưng app vẫn chạy được. Log để người vận hành thấy.
        logger.error(f"Không tạo được auth index: {e}")
