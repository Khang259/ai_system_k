"""GET /api/v1/nodes/get_runtime_state + SSE auth."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from application.container import container
from application.fe_api.runtime_nodes import GetNodeRuntimeState
from application.runtime.runtime_state_hub import RuntimeStateHub
from infrastructure.auth.jwt_service import JwtTokenService
from presentation.routes.v1.nodes import router as nodes_v1_router
from presentation.routes.v1.runtime import router as runtime_v1_router
from tests.application.fakes import FakeNodeStateStore

USER = {
    "user_id": "u-1",
    "username": "op",
    "role": "operator",
    "permissions": [],
}


def _client(monkeypatch, *, store=None):
    svc = JwtTokenService("secret-runtime-nodes")
    monkeypatch.setattr(container, "token_issuer", svc)
    state = store if store is not None else FakeNodeStateStore(ready=False)
    monkeypatch.setattr(container, "get_node_runtime_state_v1", GetNodeRuntimeState(state))
    monkeypatch.setattr(container, "runtime_state_hub", RuntimeStateHub(debounce_ms=50))

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(nodes_v1_router, prefix="/api/v1/nodes", tags=["nodes-v1"])
    app.include_router(runtime_v1_router, prefix="/api/v1/runtime", tags=["runtime-v1"])
    return TestClient(app), svc


def _auth(svc, user=USER):
    return {"Authorization": f"Bearer {svc.issue_access(user)['token']}"}


def test_get_runtime_state_empty_when_not_ready(monkeypatch):
    http, svc = _client(monkeypatch)
    res = http.get("/api/v1/nodes/get_runtime_state", headers=_auth(svc))
    assert res.status_code == 200
    body = res.json()
    assert body["runtimeReady"] is False
    assert body["items"] == []


def test_get_runtime_state_with_items(monkeypatch):
    store = FakeNodeStateStore()
    store.update_detection("start_1", True)
    store._ns.ready_start_list.add("start_1")
    http, svc = _client(monkeypatch, store=store)
    res = http.get("/api/v1/nodes/get_runtime_state", headers=_auth(svc))
    assert res.status_code == 200
    assert res.json()["runtimeReady"] is True
    assert res.json()["items"][0]["isReady"] is True


def test_access_token_query_rejected_on_runtime_state(monkeypatch):
    """CRUD/nodes chỉ Bearer — không nhận ?access_token=."""
    http, svc = _client(monkeypatch)
    token = svc.issue_access(USER)["token"]
    res = http.get(f"/api/v1/nodes/get_runtime_state?access_token={token}")
    assert res.status_code == 401


def test_openapi_access_token_only_on_sse(monkeypatch):
    """Query access_token chỉ xuất hiện trên SSE events, không trên unlock_by_order."""
    http, _ = _client(monkeypatch)
    spec = http.get("/openapi.json").json()
    paths = spec["paths"]

    unlock_params = paths["/api/v1/nodes/unlock_by_order"]["post"].get("parameters") or []
    assert not any(p.get("name") == "access_token" for p in unlock_params)

    state_params = paths["/api/v1/nodes/get_runtime_state"]["get"].get("parameters") or []
    assert not any(p.get("name") == "access_token" for p in state_params)

    events_params = paths["/api/v1/runtime/events"]["get"].get("parameters") or []
    assert any(p.get("name") == "access_token" for p in events_params)


def test_sse_rejects_missing_token(monkeypatch):
    http, _ = _client(monkeypatch)
    res = http.get("/api/v1/runtime/events")
    assert res.status_code == 401


def test_sse_route_registered(monkeypatch):
    http, _ = _client(monkeypatch)
    paths = {r.path for r in http.app.routes}
    assert "/api/v1/runtime/events" in paths
