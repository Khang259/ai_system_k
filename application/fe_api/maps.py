"""Map zip use cases — import / versions / compress / download (global)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from application.result import UseCaseResult
from infrastructure.storage.map_zip_store import MapZipStore, validate_zip_has_compress


class MapVersionStore(Protocol):
    async def insert_version(self, doc: Dict[str, Any]) -> str: ...
    async def get_by_version_id(self, version_id: str) -> Optional[Dict[str, Any]]: ...
    async def list_newest_first(self) -> List[Dict[str, Any]]: ...
    async def list_oldest_first(self) -> List[Dict[str, Any]]: ...
    async def delete_by_version_id(self, version_id: str) -> bool: ...
    async def count_all(self) -> int: ...


class MapStateStore(Protocol):
    async def get_active_version_id(self) -> Optional[str]: ...
    async def set_active_version_id(self, version_id: str) -> None: ...


def _iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return None


def _public_version(doc: Dict[str, Any], active_id: Optional[str]) -> Dict[str, Any]:
    vid = doc.get("version_id")
    return {
        "versionId": vid,
        "originalFilename": doc.get("original_filename") or "",
        "byteSize": doc.get("byte_size") or 0,
        "checksum": doc.get("checksum") or "",
        "createdAt": _iso(doc.get("created_at")),
        "createdBy": doc.get("created_by") or "",
        "isActive": vid == active_id,
    }


class ImportMap:
    def __init__(
        self,
        versions: MapVersionStore,
        state: MapStateStore,
        store: MapZipStore,
        keep: int,
        max_upload_mb: int,
    ) -> None:
        self._versions = versions
        self._state = state
        self._store = store
        self._keep = max(1, int(keep))
        self._max_bytes = max(1, int(max_upload_mb)) * 1024 * 1024

    async def execute(
        self,
        data: bytes,
        original_filename: str,
        created_by: str,
    ) -> UseCaseResult:
        if not data:
            return UseCaseResult.fail("File rỗng", http_status=400)
        if len(data) > self._max_bytes:
            return UseCaseResult.fail(
                f"File vượt quá {self._max_bytes // (1024 * 1024)}MB",
                http_status=400,
            )
        try:
            validate_zip_has_compress(data)
        except ValueError as e:
            return UseCaseResult.fail(str(e), http_status=400)

        version_id = uuid.uuid4().hex
        stored_path, byte_size, checksum = self._store.save(version_id, data)
        await self._versions.insert_version(
            {
                "version_id": version_id,
                "original_filename": original_filename or f"{version_id}.zip",
                "stored_path": stored_path,
                "byte_size": byte_size,
                "checksum": checksum,
                "created_by": created_by or "",
            }
        )
        await self._state.set_active_version_id(version_id)
        pruned = await self._prune_old()
        return UseCaseResult.ok(
            versionId=version_id,
            isActive=True,
            pruned=pruned,
            byteSize=byte_size,
            checksum=checksum,
        )

    async def _prune_old(self) -> List[str]:
        """Xoá bản cũ nhất khi số version > keep. Không xoá bản active."""
        removed: List[str] = []
        active = await self._state.get_active_version_id()
        while await self._versions.count_all() > self._keep:
            oldest_list = await self._versions.list_oldest_first()
            victim = None
            for doc in oldest_list:
                if doc.get("version_id") != active:
                    victim = doc
                    break
            if victim is None:
                break
            vid = victim["version_id"]
            path = victim.get("stored_path") or ""
            await self._versions.delete_by_version_id(vid)
            try:
                self._store.delete(path)
            except OSError:
                pass
            removed.append(vid)
        return removed


class ListMapVersions:
    def __init__(self, versions: MapVersionStore, state: MapStateStore) -> None:
        self._versions = versions
        self._state = state

    async def execute(self) -> UseCaseResult:
        active = await self._state.get_active_version_id()
        docs = await self._versions.list_newest_first()
        items = [_public_version(d, active) for d in docs]
        return UseCaseResult.ok(items=items, activeVersionId=active)


class SetActiveMap:
    def __init__(self, versions: MapVersionStore, state: MapStateStore) -> None:
        self._versions = versions
        self._state = state

    async def execute(self, version_id: str) -> UseCaseResult:
        doc = await self._versions.get_by_version_id(version_id)
        if not doc:
            return UseCaseResult.fail("Version không tồn tại", http_status=404)
        await self._state.set_active_version_id(version_id)
        return UseCaseResult.ok(versionId=version_id, isActive=True)


class GetCompress:
    def __init__(
        self,
        versions: MapVersionStore,
        state: MapStateStore,
        store: MapZipStore,
    ) -> None:
        self._versions = versions
        self._state = state
        self._store = store

    async def execute(self, version_id: Optional[str] = None) -> UseCaseResult:
        vid = version_id or await self._state.get_active_version_id()
        if not vid:
            return UseCaseResult.fail("Chưa có map active", http_status=404)
        doc = await self._versions.get_by_version_id(vid)
        if not doc:
            return UseCaseResult.fail("Version không tồn tại", http_status=404)
        try:
            compress = self._store.read_compress(doc["stored_path"])
        except FileNotFoundError:
            return UseCaseResult.fail("File zip không còn trên đĩa", http_status=404)
        except ValueError as e:
            return UseCaseResult.fail(str(e), http_status=500)
        return UseCaseResult.ok(versionId=vid, compress=compress)


class DownloadMapZip:
    def __init__(
        self,
        versions: MapVersionStore,
        state: MapStateStore,
        store: MapZipStore,
    ) -> None:
        self._versions = versions
        self._state = state
        self._store = store

    async def execute(self, version_id: Optional[str] = None) -> UseCaseResult:
        vid = version_id or await self._state.get_active_version_id()
        if not vid:
            return UseCaseResult.fail("Chưa có map active", http_status=404)
        doc = await self._versions.get_by_version_id(vid)
        if not doc:
            return UseCaseResult.fail("Version không tồn tại", http_status=404)
        try:
            raw = self._store.read_bytes(doc["stored_path"])
        except FileNotFoundError:
            return UseCaseResult.fail("File zip không còn trên đĩa", http_status=404)
        filename = doc.get("original_filename") or f"{vid}.zip"
        return UseCaseResult.ok(
            content=raw,
            filename=filename,
            media_type="application/zip",
            versionId=vid,
        )
