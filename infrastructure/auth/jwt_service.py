"""
Phát access token (JWT) + refresh token (chuỗi ngẫu nhiên).

Access token không lưu server-side, chỉ verify chữ ký → không revoke được,
nên TTL phải ngắn. Refresh token lưu **dạng hash** trong Mongo (rò DB cũng
không dùng lại được token) và revoke được khi logout.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from utils.setup_log import setup_logger

logger = setup_logger("auth", "logs/auth/log")


class JwtTokenService:
    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        access_ttl_min: int = 15,
        refresh_ttl_days: int = 7,
    ):
        if not secret:
            # Không raise: app vẫn phải chạy được khi chưa cấu hình. Đổi lại
            # mọi token mất hiệu lực sau restart — dev tiện, production sẽ
            # nhận ra ngay vì bị đăng xuất mỗi lần deploy.
            secret = secrets.token_urlsafe(48)
            logger.warning(
                "JWT_SECRET trống → dùng secret ngẫu nhiên trong bộ nhớ. "
                "Token sẽ mất hiệu lực sau mỗi lần khởi động. "
                "Đặt JWT_SECRET trong .env cho production."
            )

        self._secret = secret
        self._algorithm = algorithm
        self._access_ttl = timedelta(minutes=access_ttl_min)
        self._refresh_ttl = timedelta(days=refresh_ttl_days)

    # ── access token ─────────────────────────────────────────
    def issue_access(self, user: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        expires_at = now + self._access_ttl
        payload = {
            "sub": user["user_id"],
            "username": user.get("username", ""),
            "role": user.get("role", ""),
            "permissions": list(user.get("permissions") or []),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return {"token": token, "expires_in": int(self._access_ttl.total_seconds())}

    def decode_access(self, token: str) -> Optional[Dict[str, Any]]:
        """None khi token sai chữ ký, hết hạn hoặc hỏng — route trả 401."""
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError:
            return None

    # ── refresh token ────────────────────────────────────────
    def new_refresh(self) -> Dict[str, Any]:
        raw = secrets.token_urlsafe(48)
        return {
            "raw": raw,
            "hash": self.hash_refresh(raw),
            "expires_at": datetime.now(timezone.utc) + self._refresh_ttl,
        }

    def hash_refresh(self, raw: str) -> str:
        """
        SHA-256, không bcrypt: token đã là 48 byte ngẫu nhiên nên không cần
        chống brute force, và refresh chạy thường xuyên hơn login nhiều.
        """
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
