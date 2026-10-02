"""POST /api/v1/nodes/unlock_by_user (+ alias /unlock) — JWT, gỡ cả user+system theo nodeId."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from application.container import container
from application.result import UseCaseResult
from domain.permissions import NODE_MAINTENANCE
from presentation.routes.v1.nodes import router as nodes_v1_router


class _UnlockUC:
    def __init__(self, result: UseCaseResult):
        self.result = result
        self.calls: list = []

    async def execute(self, node_id: str, *, user: bool = True, system: bool = True):
        self.calls.append({"node_id": node_id, "user": user, "system": system})
        return self.result


class _Audit:
    def __init__(self):
        self.logs: list = []

    async def log(self, **kwargs):
        self.logs.append(kwargs)


class _Tokens:
    def decode_access(self, token: str):
        if token != "ok":
            return None
        return {
            "sub": "u1",
            "username": "op1",
            "role": "operator",
            "permissions": [NODE_MAINTENANCE],
        }


def _client(monkeypatch, unlock_result: UseCaseResult):
    unlock = _UnlockUC(unlock_result)
    audit = _Audit()
    monkeypatch.setattr(container, "unlock_v1", unlock)
    monkeypatch.setattr(container, "action_audit", audit)
    monkeypatch.setattr(container, "token_issuer", _Tokens())

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(nodes_v1_router, prefix="/api/v1/nodes", tags=["nodes-v1"])
    return TestClient(app), unlock, audit


def _auth_headers():
    return {"Authorization": "Bearer ok"}


def test_unlock_by_user_clears_both_locks(monkeypatch):
    http, unlock, audit = _client(
        monkeypatch,
        UseCaseResult.ok(
            nodeId="start_1",
            lock={"user": False, "system": False, "orderId": None},
        ),
    )
    res = http.post(
        "/api/v1/nodes/unlock_by_user",
        json={"nodeId": "start_1"},
        headers=_auth_headers(),
    )
    assert res.status_code == 200
    assert res.json()["nodeId"] == "start_1"
    assert unlock.calls == [{"node_id": "start_1", "user": True, "system": True}]
    assert audit.logs[0]["action"] == "unlock_by_user"
    assert audit.logs[0]["user"] == "op1"


def test_unlock_by_user_requires_auth(monkeypatch):
    http, _, _ = _client(
        monkeypatch,
        UseCaseResult.ok(nodeId="x", lock={"user": False, "system": False}),
    )
    res = http.post("/api/v1/nodes/unlock_by_user", json={"nodeId": "x"})
    assert res.status_code == 401
