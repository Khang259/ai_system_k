"""Alias /api/v1/runtime — confirm-ready / pause-scan + permission."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from application.container import container
from application.result import UseCaseResult
from infrastructure.auth.jwt_service import JwtTokenService
from presentation.routes.v1.runtime import router as runtime_v1_router

ADMIN = {
    "user_id": "u-2",
    "username": "admin",
    "role": "admin",
    "permissions": ["system.control"],
}

OPERATOR = {
    "user_id": "u-1",
    "username": "op",
    "role": "operator",
    "permissions": ["camera.read"],
}


class _SyncUC:
    def __init__(self, result: UseCaseResult):
        self.result = result
        self.calls = 0

    def execute(self, *args, **kwargs):
        self.calls += 1
        return self.result


def _client(monkeypatch):
    svc = JwtTokenService("secret-runtime-v1")
    monkeypatch.setattr(container, "token_issuer", svc)
    confirm = _SyncUC(
        UseCaseResult.ok(message="Scanning started", snapshot_size=1)
    )
    pause = _SyncUC(UseCaseResult.ok(message="Scanning paused"))
    status = _SyncUC(UseCaseResult.ok(running=True, inference={"paused": True}))
    monkeypatch.setattr(container, "confirm_ready", confirm)
    monkeypatch.setattr(container, "pause_scan", pause)
    monkeypatch.setattr(container, "get_runtime_status", status)

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(runtime_v1_router)
    return TestClient(app), svc, confirm, pause


def _auth(svc, user=ADMIN):
    return {"Authorization": f"Bearer {svc.issue_access(user)['token']}"}


def test_confirm_ready_and_pause_scan(monkeypatch):
    http, svc, confirm, pause = _client(monkeypatch)

    denied = http.post("/api/v1/runtime/confirm-ready", headers=_auth(svc, OPERATOR))
    assert denied.status_code == 403

    ok = http.post("/api/v1/runtime/confirm-ready", headers=_auth(svc))
    assert ok.status_code == 200
    assert ok.json()["message"] == "Scanning started"
    assert confirm.calls == 1

    paused = http.post("/api/v1/runtime/pause-scan", headers=_auth(svc))
    assert paused.status_code == 200
    assert paused.json()["message"] == "Scanning paused"
    assert pause.calls == 1


def test_get_status_needs_login_only(monkeypatch):
    http, svc, _, _ = _client(monkeypatch)
    res = http.get("/api/v1/runtime/get_status", headers=_auth(svc, OPERATOR))
    assert res.status_code == 200
    assert res.json()["inference"]["paused"] is True
