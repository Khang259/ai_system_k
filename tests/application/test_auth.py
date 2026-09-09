"""
Auth use case — login / logout / refresh / me.

Fake toàn bộ port nên không cần Mongo, không cần bcrypt thật.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from application.auth.session import GetMe, Login, Logout, RefreshSession

USER = {
    "user_id": "u-1",
    "username": "operator01",
    "name": "Nguyễn Thành",
    "role": "operator",
    "permissions": ["camera.read", "logs.read"],
    "password_hash": "hash-of-correct",
    "enabled": True,
}


class FakeUserRepo:
    def __init__(self, user=None):
        self._user = user

    async def get_by_username(self, username):
        if self._user and self._user["username"] == username:
            return dict(self._user)
        return None

    async def get_by_id(self, user_id):
        if self._user and self._user["user_id"] == user_id:
            return dict(self._user)
        return None


class FakeRefreshStore:
    def __init__(self):
        self.records = {}
        self.revoked = []

    async def save(self, user_id, token_hash, expires_at):
        # Single session: một bản ghi cho mỗi user
        self.records = {
            k: v for k, v in self.records.items() if v["user_id"] != user_id
        }
        self.records[token_hash] = {
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
        }

    async def find(self, token_hash):
        rec = self.records.get(token_hash)
        return dict(rec) if rec else None

    async def revoke_user(self, user_id):
        self.revoked.append(user_id)
        self.records = {
            k: v for k, v in self.records.items() if v["user_id"] != user_id
        }


class FakeHasher:
    def __init__(self):
        self.verify_calls = []

    def hash(self, password):
        return f"hash-of-{password}"

    def verify(self, password, hashed):
        self.verify_calls.append((password, hashed))
        return hashed == f"hash-of-{password}"

    def dummy_hash(self):
        return "hash-of-__dummy__"


class FakeTokens:
    def __init__(self):
        self.counter = 0

    def issue_access(self, user):
        return {"token": f"access-{user['user_id']}", "expires_in": 900}

    def decode_access(self, token):
        return None

    def new_refresh(self):
        self.counter += 1
        raw = f"refresh-{self.counter}"
        return {
            "raw": raw,
            "hash": self.hash_refresh(raw),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        }

    def hash_refresh(self, raw):
        return f"sha-{raw}"


class FakeAudit:
    def __init__(self, failures=0):
        self.events = []
        self.failures = failures

    async def log_event(self, username, event, ip, user_agent=""):
        self.events.append((username, event))

    async def count_recent_failures(self, username, minutes):
        return self.failures


def _login(user=USER, failures=0, max_failed=5, lockout_min=15):
    store = FakeRefreshStore()
    audit = FakeAudit(failures=failures)
    hasher = FakeHasher()
    use_case = Login(
        FakeUserRepo(user),
        FakeTokens(),
        store,
        hasher,
        audit,
        max_failed=max_failed,
        lockout_min=lockout_min,
    )
    return use_case, store, audit, hasher


# ── login ────────────────────────────────────────────────────
def test_login_ok_returns_tokens_and_public_user():
    use_case, store, audit, _ = _login()
    result = asyncio.run(use_case.execute("operator01", "correct", "10.0.0.5", "Chrome"))

    assert result.success
    assert result.data["accessToken"] == "access-u-1"
    assert result.data["refreshToken"] == "refresh-1"
    assert result.data["expiresIn"] == 900
    assert result.data["user"] == {
        "id": "u-1",
        "name": "Nguyễn Thành",
        "role": "operator",
        "permissions": ["camera.read", "logs.read"],
    }
    # Refresh token được lưu dạng hash, không lưu bản thô
    assert "sha-refresh-1" in store.records
    assert "refresh-1" not in store.records
    assert ("operator01", "login") in audit.events


def test_login_never_leaks_password_hash():
    use_case, _, _, _ = _login()
    result = asyncio.run(use_case.execute("operator01", "correct"))

    assert "password_hash" not in result.data["user"]
    assert "password_hash" not in result.data


def test_login_wrong_password_returns_401_and_logs_failure():
    use_case, _, audit, _ = _login()
    result = asyncio.run(use_case.execute("operator01", "wrong"))

    assert not result.success
    assert result.data["http_status"] == 401
    assert ("operator01", "login_failed") in audit.events


def test_login_unknown_user_still_runs_verify_to_hide_timing():
    """
    Username không tồn tại vẫn phải gọi verify (với hash giả), nếu không thì
    thời gian phản hồi tiết lộ username nào có thật.
    """
    use_case, _, _, hasher = _login(user=None)
    result = asyncio.run(use_case.execute("khong-ton-tai", "bat-ky"))

    assert not result.success
    assert result.data["http_status"] == 401
    assert hasher.verify_calls == [("bat-ky", "hash-of-__dummy__")]


def test_login_same_message_for_wrong_user_and_wrong_password():
    known, _, _, _ = _login()
    unknown, _, _, _ = _login(user=None)

    a = asyncio.run(known.execute("operator01", "wrong"))
    b = asyncio.run(unknown.execute("ai-do", "wrong"))

    assert a.error == b.error


def test_login_disabled_account_returns_403():
    use_case, _, audit, _ = _login(user={**USER, "enabled": False})
    result = asyncio.run(use_case.execute("operator01", "correct"))

    assert not result.success
    assert result.data["http_status"] == 403
    assert ("operator01", "login_disabled") in audit.events


def test_login_rate_limited_returns_429_without_checking_password():
    use_case, _, _, hasher = _login(failures=5, max_failed=5)
    result = asyncio.run(use_case.execute("operator01", "correct"))

    assert not result.success
    assert result.data["http_status"] == 429
    assert hasher.verify_calls == []  # chặn trước khi tốn công hash


def test_login_rate_limit_off_when_lockout_zero():
    use_case, _, _, _ = _login(failures=99, lockout_min=0)
    assert asyncio.run(use_case.execute("operator01", "correct")).success


def test_login_empty_credentials_rejected():
    use_case, _, _, _ = _login()
    assert not asyncio.run(use_case.execute("", "")).success


def test_login_username_is_case_insensitive():
    use_case, _, _, _ = _login()
    assert asyncio.run(use_case.execute("OPERATOR01", "correct")).success


def test_login_twice_keeps_only_latest_session():
    """Single session: máy mới đẩy máy cũ ra."""
    use_case, store, _, _ = _login()
    asyncio.run(use_case.execute("operator01", "correct"))
    asyncio.run(use_case.execute("operator01", "correct"))

    assert list(store.records) == ["sha-refresh-2"]


# ── refresh ──────────────────────────────────────────────────
def _refresh_setup(expires_in_days=7, user=USER):
    store = FakeRefreshStore()
    tokens = FakeTokens()
    asyncio.run(
        store.save(
            "u-1",
            "sha-refresh-old",
            datetime.now(timezone.utc) + timedelta(days=expires_in_days),
        )
    )
    return RefreshSession(store, FakeUserRepo(user), tokens), store


def test_refresh_rotates_token_and_invalidates_old():
    use_case, store = _refresh_setup()
    result = asyncio.run(use_case.execute("refresh-old"))

    assert result.success
    assert result.data["refreshToken"] == "refresh-1"
    # Token vừa dùng không còn hiệu lực
    assert "sha-refresh-old" not in store.records
    assert "sha-refresh-1" in store.records


def test_refresh_rejects_unknown_token():
    use_case, _ = _refresh_setup()
    result = asyncio.run(use_case.execute("khong-co-that"))

    assert not result.success
    assert result.data["http_status"] == 401


def test_refresh_rejects_expired_token_and_revokes():
    use_case, store = _refresh_setup(expires_in_days=-1)
    result = asyncio.run(use_case.execute("refresh-old"))

    assert not result.success
    assert result.data["http_status"] == 401
    assert "u-1" in store.revoked


def test_refresh_handles_naive_datetime_from_mongo():
    """
    Mongo trả datetime naive dù ta ghi bản aware — so sánh trực tiếp sẽ
    TypeError. Token còn hạn phải được chấp nhận bình thường.
    """
    store = FakeRefreshStore()
    store.records["sha-refresh-old"] = {
        "user_id": "u-1",
        "token_hash": "sha-refresh-old",
        "expires_at": datetime.utcnow() + timedelta(days=1),  # naive
    }
    use_case = RefreshSession(store, FakeUserRepo(USER), FakeTokens())

    assert asyncio.run(use_case.execute("refresh-old")).success


def test_refresh_rejects_disabled_account():
    use_case, store = _refresh_setup(user={**USER, "enabled": False})
    result = asyncio.run(use_case.execute("refresh-old"))

    assert not result.success
    assert "u-1" in store.revoked


def test_refresh_rejects_empty_token():
    use_case, _ = _refresh_setup()
    assert not asyncio.run(use_case.execute("")).success


# ── logout / me ──────────────────────────────────────────────
def test_logout_revokes_refresh_token():
    store = FakeRefreshStore()
    audit = FakeAudit()
    result = asyncio.run(Logout(store, audit).execute("u-1", "operator01", "10.0.0.5"))

    assert result.success
    assert store.revoked == ["u-1"]
    assert ("operator01", "logout") in audit.events


def test_get_me_returns_public_fields_only():
    result = asyncio.run(GetMe(FakeUserRepo(USER)).execute("u-1"))

    assert result.success
    assert result.data == {
        "id": "u-1",
        "name": "Nguyễn Thành",
        "role": "operator",
        "permissions": ["camera.read", "logs.read"],
    }


def test_get_me_unknown_user_returns_404():
    result = asyncio.run(GetMe(FakeUserRepo(None)).execute("u-999"))

    assert not result.success
    assert result.data["http_status"] == 404
