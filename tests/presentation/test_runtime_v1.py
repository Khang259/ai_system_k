"""Alias /api/v1/runtime — start-scan / confirm-dispatch / pause-scan + permission."""
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
    start = _SyncUC(UseCaseResult.ok(message="Scanning started"))
    confirm = _SyncUC(
        UseCaseResult.fail("Inference đang pause", http_status=409)
    )
    pending = _SyncUC(UseCaseResult.ok(runtimeReady=True, batch={}, nextPairs=[]))
    cancel = _SyncUC(UseCaseResult.ok(message="Batch canceled", remaining=[]))
    pause = _SyncUC(UseCaseResult.ok(message="Scanning paused"))
    status = _SyncUC(UseCaseResult.ok(running=True, inference={"paused": True}))
    monkeypatch.setattr(container, "start_scan", start)
    monkeypatch.setattr(container, "confirm_dispatch", confirm)
    monkeypatch.setattr(container, "get_pending_pairs", pending)
    monkeypatch.setattr(container, "cancel_batch", cancel)
    monkeypatch.setattr(container, "pause_scan", pause)
    monkeypatch.setattr(container, "get_runtime_status", status)

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(runtime_v1_router, prefix="/api/v1/runtime", tags=["runtime-v1"])
    return TestClient(app), svc, start, pause


def _auth(svc, user=ADMIN):
    return {"Authorization": f"Bearer {svc.issue_access(user)['token']}"}


def test_start_scan_and_pause_scan(monkeypatch):
    http, svc, start, pause = _client(monkeypatch)

    denied = http.post("/api/v1/runtime/start-scan", headers=_auth(svc, OPERATOR))
    assert denied.status_code == 403

    ok = http.post("/api/v1/runtime/start-scan", headers=_auth(svc))
    assert ok.status_code == 200
    assert ok.json()["message"] == "Scanning started"
    assert start.calls == 1

    paused = http.post("/api/v1/runtime/pause-scan", headers=_auth(svc))
    assert paused.status_code == 200
    assert paused.json()["message"] == "Scanning paused"
    assert pause.calls == 1


def test_confirm_dispatch_maps_409_and_pending_pairs_login_only(monkeypatch):
    http, svc, _, _ = _client(monkeypatch)

    denied = http.post("/api/v1/runtime/confirm-dispatch", headers=_auth(svc, OPERATOR))
    assert denied.status_code == 403

    conflict = http.post("/api/v1/runtime/confirm-dispatch", headers=_auth(svc))
    assert conflict.status_code == 409
    assert conflict.json()["message"] == "Inference đang pause"

    pending = http.get("/api/v1/runtime/get_pending_pairs", headers=_auth(svc, OPERATOR))
    assert pending.status_code == 200
    assert pending.json()["runtimeReady"] is True


def test_cancel_batch_needs_system_control(monkeypatch):
    http, svc, _, _ = _client(monkeypatch)
    denied = http.post("/api/v1/runtime/cancel-batch", headers=_auth(svc, OPERATOR))
    assert denied.status_code == 403
    ok = http.post("/api/v1/runtime/cancel-batch", headers=_auth(svc))
    assert ok.status_code == 200
    assert ok.json()["message"] == "Batch canceled"


def test_get_status_needs_login_only(monkeypatch):
    http, svc, _, _ = _client(monkeypatch)
    res = http.get("/api/v1/runtime/get_status", headers=_auth(svc, OPERATOR))
    assert res.status_code == 200
    assert res.json()["inference"]["paused"] is True
