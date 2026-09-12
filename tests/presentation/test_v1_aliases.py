"""
Alias /api/v1 — snapshot + zone/system start-stop.

Không cần GPU/Mongo: fake use case trên container + JWT thật để kiểm
permission + vỏ HTTP (message / JPEG).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from application.container import container
from application.result import UseCaseResult
from infrastructure.auth.jwt_service import JwtTokenService
from presentation.routes.v1.cameras import router as cameras_v1_router
from presentation.routes.v1.system import router as system_v1_router
from presentation.routes.v1.zones import router as zones_v1_router

OPERATOR = {
    "user_id": "u-1",
    "username": "op",
    "role": "operator",
    "permissions": ["camera.read", "zone.control"],
}

ADMIN = {
    "user_id": "u-2",
    "username": "admin",
    "role": "admin",
    "permissions": ["camera.read", "zone.control", "system.control"],
}


class _SyncUC:
    def __init__(self, result: UseCaseResult):
        self.result = result
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


class _AsyncUC:
    def __init__(self, result: UseCaseResult):
        self.result = result
        self.calls = []

    async def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def _client(monkeypatch, preview=None, start_zone=None, stop_zone=None,
            start_all=None, stop_all=None):
    svc = JwtTokenService("secret-alias-test")
    monkeypatch.setattr(container, "token_issuer", svc)

    preview_uc = preview or _SyncUC(UseCaseResult.ok(jpeg=b"\xff\xd8fake"))
    start_zone_uc = start_zone or _SyncUC(
        UseCaseResult.ok(message="Zone AE5 enabled", enabled=1)
    )
    stop_zone_uc = stop_zone or _SyncUC(
        UseCaseResult.ok(message="Zone AE5 disabled", enabled=0)
    )
    start_all_uc = start_all or _AsyncUC(
        UseCaseResult.ok(message="Cameras started", streaming=1)
    )
    stop_all_uc = stop_all or _SyncUC(UseCaseResult.ok(message="All cameras disabled"))

    monkeypatch.setattr(container, "get_camera_preview", preview_uc)
    monkeypatch.setattr(container, "start_zone_cameras", start_zone_uc)
    monkeypatch.setattr(container, "stop_zone_cameras", stop_zone_uc)
    monkeypatch.setattr(container, "start_all_cameras", start_all_uc)
    monkeypatch.setattr(container, "stop_all_cameras", stop_all_uc)

    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def as_message(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(cameras_v1_router)
    app.include_router(zones_v1_router)
    app.include_router(system_v1_router)

    return TestClient(app), svc, {
        "preview": preview_uc,
        "start_zone": start_zone_uc,
        "stop_zone": stop_zone_uc,
        "start_all": start_all_uc,
        "stop_all": stop_all_uc,
    }


def _auth(svc, user=OPERATOR):
    return {"Authorization": f"Bearer {svc.issue_access(user)['token']}"}


def test_get_snapshot_returns_jpeg(monkeypatch):
    http, svc, ucs = _client(monkeypatch)
    res = http.get("/api/v1/cameras/get_snapshot?cameraId=1", headers=_auth(svc))

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/jpeg")
    assert res.content == b"\xff\xd8fake"
    assert ucs["preview"].calls[0] == ((1,), {"detect": False})


def test_get_snapshot_maps_preview_error(monkeypatch):
    http, svc, _ = _client(
        monkeypatch,
        preview=_SyncUC(UseCaseResult.fail("Camera not streaming", http_status=409)),
    )
    res = http.get("/api/v1/cameras/get_snapshot?cameraId=9", headers=_auth(svc))

    assert res.status_code == 409
    assert res.json() == {"message": "Camera not streaming"}


def test_get_snapshot_requires_camera_read(monkeypatch):
    http, svc, _ = _client(monkeypatch)
    no_cam = {**OPERATOR, "permissions": ["zone.control"]}
    res = http.get("/api/v1/cameras/get_snapshot?cameraId=1", headers=_auth(svc, no_cam))
    assert res.status_code == 403


def test_start_stop_zone(monkeypatch):
    http, svc, ucs = _client(monkeypatch)

    start = http.post(
        "/api/v1/zones/start_zone",
        headers=_auth(svc),
        json={"zoneId": "ae5"},
    )
    assert start.status_code == 200
    assert start.json()["message"] == "Zone AE5 enabled"
    assert ucs["start_zone"].calls[0][0] == ("ae5",)

    stop = http.post(
        "/api/v1/zones/stop_zone",
        headers=_auth(svc),
        json={"zoneId": "AE5"},
    )
    assert stop.status_code == 200
    assert stop.json()["enabled"] == 0


def test_system_start_all_requires_system_control(monkeypatch):
    http, svc, _ = _client(monkeypatch)

    denied = http.post("/api/v1/system/start_all", headers=_auth(svc))
    assert denied.status_code == 403
    assert "system.control" in denied.json()["message"]

    ok = http.post("/api/v1/system/start_all", headers=_auth(svc, ADMIN))
    assert ok.status_code == 200
    assert ok.json()["streaming"] == 1


def test_system_stop_all(monkeypatch):
    http, svc, ucs = _client(monkeypatch)
    res = http.post("/api/v1/system/stop_all", headers=_auth(svc, ADMIN))

    assert res.status_code == 200
    assert res.json()["message"] == "All cameras disabled"
    assert len(ucs["stop_all"].calls) == 1


def test_system_start_all_fail_is_503(monkeypatch):
    http, svc, _ = _client(
        monkeypatch,
        start_all=_AsyncUC(UseCaseResult.fail("System not initialized")),
    )
    res = http.post("/api/v1/system/start_all", headers=_auth(svc, ADMIN))
    assert res.status_code == 503
    assert res.json()["message"] == "System not initialized"


def test_get_health_ok(monkeypatch):
    http, svc, _ = _client(monkeypatch)
    monkeypatch.setattr(
        container,
        "get_health",
        _AsyncUC(
            UseCaseResult.ok(
                status="ok",
                service="AMR Camera System",
                mongo=True,
                runtime_running=True,
                webrtc={"alive": True},
            )
        ),
    )
    res = http.get("/api/v1/system/get_health", headers=_auth(svc))
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["mongo"] is True


def test_get_health_degraded_keeps_body(monkeypatch):
    http, svc, _ = _client(monkeypatch)
    monkeypatch.setattr(
        container,
        "get_health",
        _AsyncUC(
            UseCaseResult.fail(
                "degraded: runtime không sẵn sàng",
                status="degraded",
                service="AMR Camera System",
                mongo=True,
                runtime_running=False,
                webrtc={"alive": False},
            )
        ),
    )
    res = http.get("/api/v1/system/get_health", headers=_auth(svc))
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "degraded"
    assert body["mongo"] is True
    assert "message" in body


def test_get_health_requires_bearer(monkeypatch):
    http, _, _ = _client(monkeypatch)
    res = http.get("/api/v1/system/get_health")
    assert res.status_code == 401
