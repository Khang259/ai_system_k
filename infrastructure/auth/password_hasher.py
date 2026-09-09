"""
Hash mật khẩu bằng bcrypt.

Dùng `bcrypt` trực tiếp, không qua passlib: bớt một lớp phụ thuộc và tránh
lỗi tương thích đã biết giữa passlib 1.7.x với bcrypt >= 4.1.
"""
from __future__ import annotations

import bcrypt

# Hash thật của một chuỗi vô nghĩa, dùng khi username không tồn tại.
# Mục đích: giữ thời gian phản hồi của "sai username" gần bằng "sai mật khẩu".
# Không có nó thì kẻ tấn công đo thời gian là dò được username nào có thật —
# rate limit theo username không chặn được vì mỗi username chỉ cần thử 1 lần.
DUMMY_HASH = "$2b$12$ywnDQLin.C86B3hx4MCBSem0BW2di78f0kwt9M7DjhK2vinwtj12i"


class BcryptHasher:
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify(self, password: str, hashed: str) -> bool:
        if not hashed:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except (ValueError, TypeError):
            # Hash trong DB bị hỏng / sai định dạng → coi như không khớp
            return False

    def dummy_hash(self) -> str:
        return DUMMY_HASH
