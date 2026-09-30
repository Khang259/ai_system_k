"""
Seed 3 user mặc định vào Mongo (chưa có endpoint đăng ký).

Dùng pymongo đồng bộ như scripts/seed_db.py — script chạy tay, không qua app.

    uv run python scripts/seed_users.py

- User mới: hỏi mật khẩu chung, tạo document đủ field.
- User đã có: **đồng bộ `permissions` theo role** (vd. thêm map.read/map.write)
  mà không đụng mật khẩu. Token cũ hết hạn mới nhận quyền mới.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from uuid import uuid4

# Cho phép import package của dự án khi chạy trực tiếp file này
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings
from domain.permissions import permissions_for_role
from infrastructure.auth.password_hasher import BcryptHasher

MIN_PASSWORD_LEN = 8

# Bộ seed mặc định — 1 user / role trong ROLE_PERMISSIONS
DEFAULT_USERS = (
    {"username": "admin", "role": "admin", "name": "Administrator"},
    {"username": "operator", "role": "operator", "name": "Operator"},
    {"username": "viewer", "role": "viewer", "name": "Viewer"},
)


def _read_password() -> str:
    password = getpass("Mật khẩu chung cho bộ seed (chỉ dùng khi tạo user mới): ")
    if len(password) < MIN_PASSWORD_LEN:
        print(f"❌ Mật khẩu phải từ {MIN_PASSWORD_LEN} ký tự")
        return ""
    if password != getpass("Nhập lại: "):
        print("❌ Hai lần nhập không giống nhau")
        return ""
    return password


def _build_doc(spec: dict, password_hash: str) -> dict:
    role = spec["role"]
    return {
        "user_id": f"u-{uuid4().hex[:12]}",
        "username": spec["username"],
        "name": spec["name"],
        "role": role,
        "permissions": permissions_for_role(role),
        "password_hash": password_hash,
        "enabled": True,
        "created_at": datetime.now(timezone.utc),
    }


def _perm_diff(old: list, new: list) -> tuple[list, list]:
    old_s, new_s = set(old or []), set(new or [])
    return sorted(new_s - old_s), sorted(old_s - new_s)


def main() -> int:
    client = MongoClient(settings.MONGODB_URL)
    users = client[settings.MONGODB_DB]["users"]

    need_create = [
        spec
        for spec in DEFAULT_USERS
        if not users.find_one({"username": spec["username"]})
    ]

    password_hash = None
    if need_create:
        password = _read_password()
        if not password:
            client.close()
            return 1
        password_hash = BcryptHasher().hash(password)
    else:
        print("ℹ  Cả 3 user đã có — chỉ đồng bộ permissions theo role (không hỏi mật khẩu).\n")

    created = 0
    updated = 0
    unchanged = 0

    for spec in DEFAULT_USERS:
        username = spec["username"]
        role = spec["role"]
        wanted = permissions_for_role(role)
        existing = users.find_one({"username": username})

        if existing:
            old = list(existing.get("permissions") or [])
            added, removed = _perm_diff(old, wanted)
            if not added and not removed:
                print(f"✓  '{username}' permissions đã khớp role={role}")
                unchanged += 1
                continue

            users.update_one(
                {"username": username},
                {
                    "$set": {
                        "permissions": wanted,
                        "role": role,
                        "name": spec["name"],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            print(f"🔄 '{username}' cập nhật permissions (role={role})")
            if added:
                print(f"   + {', '.join(added)}")
            if removed:
                print(f"   − {', '.join(removed)}")
            updated += 1
            continue

        doc = _build_doc(spec, password_hash)
        users.insert_one(doc)
        print(f"✅ '{username}' (role={doc['role']}, id={doc['user_id']})")
        print(f"   Quyền: {', '.join(doc['permissions'])}")
        created += 1

    client.close()

    print(f"\n📊 Tạo mới: {created} · Cập nhật quyền: {updated} · Giữ nguyên: {unchanged}")
    if updated:
        print(
            "   ⚠ Token access cũ vẫn mang permissions cũ cho tới khi hết hạn "
            f"(~{settings.ACCESS_TOKEN_TTL_MIN} phút) hoặc login / refresh lại."
        )
    if created:
        print("\n   Thử đăng nhập:")
        print(
            f'   curl -X POST http://127.0.0.1:{settings.API_SERVER_PORT}/api/v1/auth/login '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"username":"admin","password":"..."}}\''
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
