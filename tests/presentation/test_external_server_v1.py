"""POST /api/v1/external_server/unlock_by_order_status — không JWT (webhook ICS)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from application.container import container
from application.result import UseCaseResult
from presentation.routes.v1.external_server import router as external_server_v1_router

URL = "/api/v1/external_server/unlock_by_order_status"
ORDER = "S-10000061-10000761-2026-10-03 09:51:33.123456"


class _UnlockUC:
    def __init__(self, result: UseCaseResult):
        self.result = result
        self.calls: list = []

    async def execute(self, order_id: str, status: int):
        self.calls.append((order_id, status))
        return self.result


class _SystemAudit:
    def __init__(self):
        self.logs: list = []

    async def log(self, **kwargs):
        self.logs.append(kwargs)


def _client(monkeypatch, result: UseCaseResult):
    uc = _UnlockUC(result)
    audit = _SystemAudit()
    monkeypatch.setattr(container, "unlock_by_order_status_v1", uc)
    monkeypatch.setattr(container, "system_action_audit", audit)

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(external_server_v1_router, prefix="/api/v1/external_server")
    return TestClient(app), uc, audit


def _body(status: int = 6):
    """Body phẳng — status int + field thừa."""
    return {
        "orderId": ORDER,
        "status": status,
        "deviceCode": "EE49822BAK00001",
        "qrContent": "10000061",
    }


def test_webhook_ok_without_auth(monkeypatch):
    http, uc, audit = _client(
        monkeypatch, UseCaseResult.ok(message="ok", orderId=ORDER, status="inprogress")
    )
    res = http.post(URL, json=_body(6))

    assert res.status_code == 200
    assert uc.calls == [(ORDER, 6)]
    assert audit.logs[0]["action"] == "unlock_by_order_status"
    assert audit.logs[0]["order_id"] == ORDER
    assert audit.logs[0]["payload"]["deviceCode"] == "EE49822BAK00001"


def test_webhook_accepts_status_23(monkeypatch):
    http, uc, _ = _client(monkeypatch, UseCaseResult.ok(message="ok", orderId=ORDER))
    res = http.post(URL, json=_body(23))

    assert res.status_code == 200
    assert uc.calls == [(ORDER, 23)]


def test_webhook_coerces_numeric_string_status(monkeypatch):
    """Pydantic v2: "23" → int 23 vẫn OK."""
    http, uc, _ = _client(monkeypatch, UseCaseResult.ok(message="ok", orderId=ORDER))
    res = http.post(URL, json={"orderId": ORDER, "status": "23"})

    assert res.status_code == 200
    assert uc.calls == [(ORDER, 23)]


def test_webhook_fail_is_400_and_logged(monkeypatch):
    http, _, audit = _client(monkeypatch, UseCaseResult.fail("orderId NOPE not found"))
    res = http.post(URL, json=_body(23))

    assert res.status_code == 400
    assert "NOPE" in res.json()["message"]
    assert audit.logs[0]["status"] == 400


def test_webhook_rejects_missing_order_id(monkeypatch):
    http, uc, _ = _client(monkeypatch, UseCaseResult.ok())
    res = http.post(URL, json={"status": 6})

    assert res.status_code == 422
    assert uc.calls == []


def test_webhook_rejects_non_numeric_status(monkeypatch):
    http, uc, _ = _client(monkeypatch, UseCaseResult.ok())
    res = http.post(URL, json={"orderId": ORDER, "status": "abc"})

    assert res.status_code == 422
    assert uc.calls == []


def test_webhook_openapi_has_no_security(monkeypatch):
    http, _, _ = _client(monkeypatch, UseCaseResult.ok())
    op = http.get("/openapi.json").json()["paths"][URL]["post"]
    assert "security" not in op or op.get("security") in (None, [], [{}])
