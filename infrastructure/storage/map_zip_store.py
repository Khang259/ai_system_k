"""
Lưu zip map nguyên bản; đọc compress.json từ trong zip (không giải nén cả archive).
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def find_compress_entry(names: list) -> Optional[str]:
    """Entry kết thúc bằng `/compress.json` (vd. compress/compress.json)."""
    for name in names:
        normalized = name.replace("\\", "/")
        if normalized.endswith("/compress.json"):
            return name
    return None


def validate_zip_has_compress(data: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Mở zip trong bộ nhớ, tìm compress.json, parse JSON.

    Returns: (entry_name, compress_dict)
    Raises: ValueError với message tiếng Việt cho API.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError("File không phải ZIP hợp lệ") from e

    with zf:
        entry = find_compress_entry(zf.namelist())
        if not entry:
            raise ValueError(
                "ZIP thiếu compress.json (cần path dạng …/compress.json)"
            )
        try:
            raw = zf.read(entry)
            compress = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("compress.json không phải JSON hợp lệ") from e
        if not isinstance(compress, dict):
            raise ValueError("compress.json phải là object JSON")
        if "nodeArr" not in compress and "nodeKeys" not in compress:
            raise ValueError("compress.json thiếu cấu trúc node (nodeKeys/nodeArr)")
    return entry, compress


class MapZipStore:
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, version_id: str) -> Path:
        # Chỉ tên file an toàn — version_id do hệ thống sinh (uuid hex)
        safe = "".join(c for c in version_id if c.isalnum() or c in "-_")
        return self.root / f"{safe}.zip"

    def save(self, version_id: str, data: bytes) -> Tuple[str, int, str]:
        path = self.path_for(version_id)
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        return str(path), len(data), digest

    def read_bytes(self, stored_path: str) -> bytes:
        path = Path(stored_path).resolve()
        root = self.root.resolve()
        try:
            path.relative_to(root)
        except ValueError as e:
            raise FileNotFoundError("Đường dẫn zip ngoài thư mục map") from e
        if not path.is_file():
            raise FileNotFoundError("File zip không tồn tại")
        return path.read_bytes()

    def read_compress(self, stored_path: str) -> Dict[str, Any]:
        data = self.read_bytes(stored_path)
        _, compress = validate_zip_has_compress(data)
        return compress

    def delete(self, stored_path: str) -> None:
        path = Path(stored_path)
        if path.is_file():
            path.unlink()
