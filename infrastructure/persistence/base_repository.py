"""
Base repository — CRUD chung cho tất cả collections.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.persistence.db import get_collection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(doc: Dict) -> Dict:
    """ObjectId → field `id` (str) để FE dùng làm React key."""
    if not doc:
        return doc
    out = dict(doc)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    return out


class BaseRepository:
    def __init__(self, collection_name: str):
        self._col_name = collection_name

    def _col(self):
        return get_collection(self._col_name)

    async def find_one(self, query: Dict) -> Optional[Dict]:
        doc = await self._col().find_one(query, {"_id": 0})
        return doc

    async def find_many(
        self,
        query: Dict,
        sort: Optional[List] = None,
        limit: int = 0,
    ) -> List[Dict]:
        cursor = self._col().find(query, {"_id": 0})
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=None)

    async def find_page(
        self,
        query: Dict,
        page: int = 1,
        page_size: int = 20,
        sort: Optional[List] = None,
    ) -> Tuple[List[Dict], int]:
        """
        Phân trang page-based. Giữ `_id` rồi đổi thành `id` qua `_serialize`.

        `find_many` / `find_one` vẫn bỏ `_id` để không phá code cũ.
        """
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))
        skip = (page - 1) * page_size
        total = await self.count(query)
        cursor = self._col().find(query)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return [_serialize(d) for d in docs], total

    async def insert_one(self, doc: Dict) -> str:
        doc["created_at"] = _now()
        result = await self._col().insert_one(doc)
        return str(result.inserted_id)

    async def update_one(self, query: Dict, data: Dict) -> bool:
        data["updated_at"] = _now()
        result = await self._col().update_one(query, {"$set": data})
        return result.modified_count > 0

    async def delete_one(self, query: Dict) -> bool:
        result = await self._col().delete_one(query)
        return result.deleted_count > 0

    async def count(self, query: Dict) -> int:
        return await self._col().count_documents(query)
