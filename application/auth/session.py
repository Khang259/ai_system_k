"""
Use case phiên đăng nhập — login / logout / refresh / me.

Cơ chế (chốt 2026-09-09): access token ngắn hạn không lưu server-side, refresh
token lưu dạng hash trong Mongo. Single session — đăng nhập máy mới đẩy máy cũ ra.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from application.ports import (
    AuthAuditPort,
    PasswordHasher,
    RefreshTokenStore,
    TokenIssuer,
    UserRepositoryPort,
)
from application.result import UseCaseResult

# Một thông báo cho cả "sai username" và "sai mật khẩu": nói rõ cái nào sai là
# tặng kẻ tấn công danh sách username có thật.
_INVALID_CREDENTIALS = "Invalid username or password"


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Chỉ field FE cần. Tuyệt đối không để `password_hash` lọt ra ngoài."""
    return {
        "id": user.get("user_id", ""),
        "name": user.get("name") or user.get("username", ""),
        "role": user.get("role", ""),
        "permissions": list(user.get("permissions") or []),
    }


def _is_expired(expires_at: Optional[datetime]) -> bool:
    """
    Mongo trả datetime **naive** dù ta ghi vào bản aware (UTC), nên phải gắn
    lại tzinfo trước khi so sánh — không thì so aware với naive là TypeError.
    """
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


class Login:
    def __init__(
        self,
        users: UserRepositoryPort,
        tokens: TokenIssuer,
        refresh_store: RefreshTokenStore,
        hasher: PasswordHasher,
        audit: AuthAuditPort,
        max_failed: int = 5,
        lockout_min: int = 15,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._refresh = refresh_store
        self._hasher = hasher
        self._audit = audit
        self._max_failed = max_failed
        self._lockout_min = lockout_min

    async def execute(
        self, username: str, password: str, ip: str = "", user_agent: str = ""
    ) -> UseCaseResult:
        username = (username or "").lower().strip()
        if not username or not password:
            return UseCaseResult.fail(_INVALID_CREDENTIALS, http_status=401)

        if self._lockout_min > 0:
            failures = await self._audit.count_recent_failures(
                username, self._lockout_min
            )
            if failures >= self._max_failed:
                return UseCaseResult.fail(
                    f"Quá nhiều lần đăng nhập sai. Thử lại sau {self._lockout_min} phút.",
                    http_status=429,
                )

        user = await self._users.get_by_username(username)

        # Username không tồn tại vẫn chạy verify với hash giả, để thời gian
        # phản hồi không tiết lộ username nào có thật.
        stored_hash = user.get("password_hash", "") if user else self._hasher.dummy_hash()
        password_ok = self._hasher.verify(password, stored_hash)

        if user is None or not password_ok:
            await self._audit.log_event(username, "login_failed", ip, user_agent)
            return UseCaseResult.fail(_INVALID_CREDENTIALS, http_status=401)

        if not user.get("enabled", True):
            await self._audit.log_event(username, "login_disabled", ip, user_agent)
            return UseCaseResult.fail("Tài khoản đã bị vô hiệu hoá", http_status=403)

        access = self._tokens.issue_access(user)
        refresh = self._tokens.new_refresh()
        await self._refresh.save(user["user_id"], refresh["hash"], refresh["expires_at"])
        await self._audit.log_event(username, "login", ip, user_agent)

        return UseCaseResult.ok(
            accessToken=access["token"],
            refreshToken=refresh["raw"],
            expiresIn=access["expires_in"],
            user=public_user(user),
        )


class Logout:
    def __init__(self, refresh_store: RefreshTokenStore, audit: AuthAuditPort) -> None:
        self._refresh = refresh_store
        self._audit = audit

    async def execute(
        self, user_id: str, username: str = "", ip: str = ""
    ) -> UseCaseResult:
        """
        Xoá refresh token → không gia hạn được nữa.

        Access token đang giữ vẫn dùng được tới khi hết hạn (tối đa
        ACCESS_TOKEN_TTL_MIN). Đây là đánh đổi đã chấp nhận khi chọn cơ chế
        này; muốn cắt ngay thì phải blacklist access token ở mọi request.
        """
        await self._refresh.revoke_user(user_id)
        await self._audit.log_event(username, "logout", ip)
        return UseCaseResult.ok()


class RefreshSession:
    def __init__(
        self,
        refresh_store: RefreshTokenStore,
        users: UserRepositoryPort,
        tokens: TokenIssuer,
    ) -> None:
        self._refresh = refresh_store
        self._users = users
        self._tokens = tokens

    async def execute(self, refresh_token: str) -> UseCaseResult:
        if not refresh_token:
            return UseCaseResult.fail("Refresh token không hợp lệ", http_status=401)

        record = await self._refresh.find(self._tokens.hash_refresh(refresh_token))
        if record is None:
            return UseCaseResult.fail("Refresh token không hợp lệ", http_status=401)

        if _is_expired(record.get("expires_at")):
            await self._refresh.revoke_user(record["user_id"])
            return UseCaseResult.fail("Phiên đã hết hạn, đăng nhập lại", http_status=401)

        user = await self._users.get_by_id(record["user_id"])
        if user is None or not user.get("enabled", True):
            await self._refresh.revoke_user(record["user_id"])
            return UseCaseResult.fail("Tài khoản không còn hiệu lực", http_status=401)

        # Rotation: cấp cặp mới và ghi đè bản cũ. Refresh token vừa dùng lập
        # tức vô hiệu, nên nếu bị lộ thì kẻ trộm chỉ dùng được một lần.
        access = self._tokens.issue_access(user)
        new_refresh = self._tokens.new_refresh()
        await self._refresh.save(
            user["user_id"], new_refresh["hash"], new_refresh["expires_at"]
        )

        return UseCaseResult.ok(
            accessToken=access["token"],
            refreshToken=new_refresh["raw"],
            expiresIn=access["expires_in"],
            user=public_user(user),
        )


class GetMe:
    def __init__(self, users: UserRepositoryPort) -> None:
        self._users = users

    async def execute(self, user_id: str) -> UseCaseResult:
        user = await self._users.get_by_id(user_id)
        if user is None:
            return UseCaseResult.fail("Không tìm thấy user", http_status=404)
        return UseCaseResult.ok(**public_user(user))
