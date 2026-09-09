"""
Tạo user đầu tiên cho hệ thống (chưa có endpoint đăng ký).

Dùng pymongo đồng bộ như scripts/seed_db.py — script chạy tay, không qua app.

    uv run python scripts/seed_users.py --username admin --role admin
    uv run python scripts/seed_users.py --username ca1 --role operator --name "Ca 1"

Mật khẩu nhập qua prompt ẩn. Không truyền mật khẩu bằng tham số dòng lệnh vì nó
lưu lại trong history của shell.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from uuid import uuid4

# Cho phép import package của dự án khi chạy trực tiếp file này
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings
from domain.permissions import ROLE_PERMISSIONS, permissions_for_role
from infrastructure.auth.password_hasher import BcryptHasher

MIN_PASSWORD_LEN = 8


def _read_password() -> str:
    password = getpass("Mật khẩu: ")
    if len(password) < MIN_PASSWORD_LEN:
        print(f"❌ Mật khẩu phải từ {MIN_PASSWORD_LEN} ký tự")
        return ""
    if password != getpass("Nhập lại: "):
        print("❌ Hai lần nhập không giống nhau")
        return ""
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo user cho Kortek")
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--role",
        default="admin",
        choices=sorted(ROLE_PERMISSIONS.keys()),
    )
    parser.add_argument("--name", default="", help="Tên hiển thị; trống = username")
    args = parser.parse_args()

    username = args.username.lower().strip()
    if not username:
        print("❌ username trống")
        return 1

    client = MongoClient(settings.MONGODB_URL)
    users = client[settings.MONGODB_DB]["users"]

    if users.find_one({"username": username}):
        print(f"❌ User '{username}' đã tồn tại — script này không ghi đè")
        client.close()
        return 1

    password = _read_password()
    if not password:
        client.close()
        return 1

    permissions = permissions_for_role(args.role)
    doc = {
        "user_id": f"u-{uuid4().hex[:12]}",
        "username": username,
        "name": args.name.strip() or username,
        "role": args.role,
        "permissions": permissions,
        "password_hash": BcryptHasher().hash(password),
        "enabled": True,
        "created_at": datetime.now(timezone.utc),
    }
    users.insert_one(doc)
    client.close()

    print(f"✅ Đã tạo user '{username}' (role={args.role}, id={doc['user_id']})")
    print(f"   Quyền: {', '.join(permissions)}")
    print("\n   Thử đăng nhập:")
    print(
        f'   curl -X POST http://127.0.0.1:{settings.API_SERVER_PORT}/api/v1/auth/login '
        f'-H "Content-Type: application/json" '
        f"-d '{{\"username\":\"{username}\",\"password\":\"...\"}}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
