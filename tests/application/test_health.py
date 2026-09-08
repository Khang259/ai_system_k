"""Health check — Mongo + runtime bắt buộc, MediaMTX chỉ report."""
import asyncio

from application.runtime.health import GetHealth
from tests.application.fakes import (
    FakeDbHealth,
    FakeRuntimeControl,
    FakeWebrtcRunner,
)


def _health(mongo_ok=True, running=True, mtx_alive=True):
    rt = FakeRuntimeControl()
    rt.running = running
    use_case = GetHealth(
        FakeDbHealth(ok=mongo_ok),
        rt,
        FakeWebrtcRunner(alive=mtx_alive),
    )
    return asyncio.run(use_case.execute())


def test_health_ok_when_mongo_and_runtime_up():
    result = _health()
    assert result.success
    assert result.data["status"] == "ok"
    assert result.data["mongo"] is True
    assert result.data["runtime_running"] is True


def test_health_degraded_when_mongo_down():
    result = _health(mongo_ok=False)
    assert not result.success
    assert result.data["status"] == "degraded"
    assert "mongo" in result.error


def test_health_degraded_when_runtime_stopped():
    result = _health(running=False)
    assert not result.success
    assert "runtime" in result.error


def test_health_still_ok_when_mediamtx_down():
    """MediaMTX optional — chết không làm health fail, chỉ report alive=False."""
    result = _health(mtx_alive=False)
    assert result.success
    assert result.data["webrtc"]["alive"] is False
