"""POST /api/v1/nodes/unlock_by_order — không JWT (external/ICS), reuse reset_flags."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from application.container import container
from application.result import UseCaseResult
from domain.models import ResetStatus
from presentation.routes.v1.nodes import router as nodes_v1_router


class _ResetUC:
    def __init__(self, result: UseCaseResult):
        self.result = result
        self.calls: list = []

    def execute(self, order_id: str, status: int):
        self.calls.append((order_id, status))
        return self.result


class _Audit:
    def __init__(self):
        self.logs: list = []

    async def log(self, **kwargs):
        self.logs.append(kwargs)


def _client(monkeypatch, reset_result: UseCaseResult):
    reset = _ResetUC(reset_result)
    audit = _Audit()
    monkeypatch.setattr(container, "reset_flags", reset)
    monkeypatch.setattr(container, "action_audit", audit)

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(nodes_v1_router, prefix="/api/v1/nodes", tags=["nodes-v1"])
    return TestClient(app), reset, audit


def test_unlock_by_order_ok_without_auth(monkeypatch):
    http, reset, audit = _client(
        monkeypatch,
        UseCaseResult.ok(message="Flags reset for orderId ORD-1", orderId="ORD-1"),
    )
    res = http.post(
        "/api/v1/nodes/unlock_by_order",
        json={"orderId": "ORD-1", "status": int(ResetStatus.COMPLETED)},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["orderId"] == "ORD-1"
    assert "Flags reset" in body["message"]
    assert reset.calls == [("ORD-1", 3)]
    assert audit.logs[0]["user"] == "external"
    assert audit.logs[0]["action"] == "unlock_by_order"


def test_unlock_by_order_empty_status(monkeypatch):
    http, reset, _ = _client(
        monkeypatch,
        UseCaseResult.ok(
            message="Empty pairs reset for orderId ORD-2",
            orderId="ORD-2",
            reset_pairs=[["start_e", "end_e"]],
        ),
    )
    res = http.post(
        "/api/v1/nodes/unlock_by_order",
        json={"orderId": "ORD-2", "status": int(ResetStatus.EMPTY_DONE)},
    )
    assert res.status_code == 200
    assert res.json()["reset_pairs"] == [["start_e", "end_e"]]
    assert reset.calls == [("ORD-2", 23)]


def test_unlock_by_order_openapi_has_no_security(monkeypatch):
    http, _, _ = _client(monkeypatch, UseCaseResult.ok(message="ok", orderId="x"))
    spec = http.get("/openapi.json").json()
    op = spec["paths"]["/api/v1/nodes/unlock_by_order"]["post"]
    assert not op.get("security")
    params = op.get("parameters") or []
    assert not any(p.get("name") == "access_token" for p in params)


def test_unlock_by_order_fail_when_order_missing(monkeypatch):
    http, reset, _ = _client(
        monkeypatch, UseCaseResult.fail("orderId NOPE not found")
    )
    res = http.post(
        "/api/v1/nodes/unlock_by_order",
        json={"orderId": "NOPE", "status": 3},
    )
    assert res.status_code == 400
    assert "not found" in res.json()["message"]
    assert reset.calls == [("NOPE", 3)]
