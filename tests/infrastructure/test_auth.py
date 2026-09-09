"""
JWT service, bcrypt hasher, và dependency xác thực ở tầng presentation.

Không cần Mongo: chỉ kiểm phần token + parse header + kiểm quyền.
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("jwt")
pytest.importorskip("bcrypt")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse

from application.container import container
from infrastructure.auth.jwt_service import JwtTokenService
from infrastructure.auth.password_hasher import DUMMY_HASH, BcryptHasher
from presentation.deps import current_user, require_permission

USER = {
    "user_id": "u-1",
    "username": "operator01",
    "role": "operator",
    "permissions": ["camera.read"],
}


# ── JWT service ──────────────────────────────────────────────
def test_access_token_roundtrip_carries_claims():
    svc = JwtTokenService("secret-a", access_ttl_min=15)
    issued = svc.issue_access(USER)

    assert issued["expires_in"] == 900
    claims = svc.decode_access(issued["token"])
    assert claims["sub"] == "u-1"
    assert claims["username"] == "operator01"
    assert claims["permissions"] == ["camera.read"]


def test_token_from_other_secret_is_rejected():
    token = JwtTokenService("secret-a").issue_access(USER)["token"]
    assert JwtTokenService("secret-b").decode_access(token) is None


def test_expired_token_is_rejected():
    svc = JwtTokenService("secret-a", access_ttl_min=0)
    token = svc.issue_access(USER)["token"]
    time.sleep(1.1)  # exp tính theo giây nên phải chờ qua mốc
    assert svc.decode_access(token) is None


def test_garbage_token_returns_none_not_raise():
    svc = JwtTokenService("secret-a")
    assert svc.decode_access("khong-phai-jwt") is None
    assert svc.decode_access("") is None


def test_empty_secret_still_works_with_generated_one():
    """JWT_SECRET trống không được làm app sập — chỉ sinh secret tạm."""
    svc = JwtTokenService("")
    token = svc.issue_access(USER)["token"]
    assert svc.decode_access(token) is not None
    # Instance khác = secret khác → token không dùng chéo được
    assert JwtTokenService("").decode_access(token) is None


def test_refresh_token_is_random_and_stored_hashed():
    svc = JwtTokenService("secret-a")
    a, b = svc.new_refresh(), svc.new_refresh()

    assert a["raw"] != b["raw"]
    assert a["hash"] != a["raw"]
    assert svc.hash_refresh(a["raw"]) == a["hash"]
    assert len(a["hash"]) == 64  # sha256 hex


# ── password hasher ──────────────────────────────────────────
def test_hash_verifies_and_salts_differ():
    hasher = BcryptHasher()
    first = hasher.hash("mat-khau-dai")

    assert hasher.verify("mat-khau-dai", first)
    assert not hasher.verify("mat-khau-sai", first)
    # Salt ngẫu nhiên → hai hash của cùng mật khẩu phải khác nhau
    assert first != hasher.hash("mat-khau-dai")


def test_verify_handles_broken_hash_without_raising():
    hasher = BcryptHasher()
    assert not hasher.verify("bat-ky", "")
    assert not hasher.verify("bat-ky", "khong-phai-bcrypt-hash")


def test_dummy_hash_is_valid_bcrypt_so_timing_matches():
    """Hash giả phải hợp lệ, nếu không verify sẽ thoát sớm và mất tác dụng."""
    hasher = BcryptHasher()
    assert hasher.dummy_hash() == DUMMY_HASH
    assert not hasher.verify("bat-ky", hasher.dummy_hash())


# ── dependency xác thực ──────────────────────────────────────
@pytest.fixture
def client(monkeypatch):
    svc = JwtTokenService("secret-test")
    monkeypatch.setattr(container, "token_issuer", svc)

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    @app.get("/who")
    def who(user=Depends(current_user)):
        return user

    @app.get("/needs-write")
    def needs_write(user=Depends(require_permission("camera.write"))):
        return {"ok": True}

    @app.get("/needs-read")
    def needs_read(user=Depends(require_permission("camera.read"))):
        return {"ok": True}

    return TestClient(app), svc


def _auth(svc, user=USER):
    return {"Authorization": f"Bearer {svc.issue_access(user)['token']}"}


def test_valid_token_exposes_claims(client):
    http, svc = client
    res = http.get("/who", headers=_auth(svc))

    assert res.status_code == 200
    assert res.json() == {
        "user_id": "u-1",
        "username": "operator01",
        "role": "operator",
        "permissions": ["camera.read"],
    }


def test_missing_header_returns_401_with_message_key(client):
    http, _ = client
    res = http.get("/who")

    assert res.status_code == 401
    # FE mong {"message": ...}, không phải {"detail": ...}
    assert "message" in res.json()
    assert "detail" not in res.json()


def test_wrong_scheme_returns_401(client):
    http, svc = client
    token = svc.issue_access(USER)["token"]

    assert http.get("/who", headers={"Authorization": token}).status_code == 401
    assert (
        http.get("/who", headers={"Authorization": f"Basic {token}"}).status_code == 401
    )
    assert http.get("/who", headers={"Authorization": "Bearer "}).status_code == 401


def test_invalid_token_returns_401(client):
    http, _ = client
    res = http.get("/who", headers={"Authorization": "Bearer rac-ruoi"})
    assert res.status_code == 401


def test_permission_granted_and_denied(client):
    http, svc = client

    assert http.get("/needs-read", headers=_auth(svc)).status_code == 200

    denied = http.get("/needs-write", headers=_auth(svc))
    assert denied.status_code == 403
    assert "camera.write" in denied.json()["message"]


def test_permission_checked_per_user_not_role(client):
    """Đổi mảng permissions là đủ, không cần sửa code theo role."""
    http, svc = client
    promoted = {**USER, "permissions": ["camera.read", "camera.write"]}

    assert http.get("/needs-write", headers=_auth(svc, promoted)).status_code == 200
