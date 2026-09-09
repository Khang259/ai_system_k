"""
RuntimeService — rollback khi khởi động thất bại.

Trước đây `_components` chỉ được gán ở CUỐI `start()`, nên nếu bước giữa nổ thì
những component đã chạy (thread + VRAM của InferenceEngine) không ai dọn, và
lần `reload()` sau tạo thêm một engine nữa. Test này khoá hành vi đó lại.
"""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("torch")

from application.container import container
from application.runtime import runtime_service as rs_module
from application.runtime.runtime_service import RuntimeService


class FakeComponent:
    """Ghi lại việc bị stop để test khẳng định được là đã dọn."""

    instances = []

    def __init__(self, *args, fail_on_start=False, **kwargs):
        self.started = False
        self.stopped = False
        self.fail_on_start = fail_on_start
        FakeComponent.instances.append(self)

    def start(self):
        if self.fail_on_start:
            raise RuntimeError("GPU không khả dụng")
        self.started = True

    def stop(self):
        self.stopped = True

    def get_status(self):
        return {"total": 0, "enabled": 0, "alive": 0}


@pytest.fixture
def patched(monkeypatch):
    FakeComponent.instances = []

    async def no_cameras():
        return []

    async def no_pairs():
        return []

    monkeypatch.setattr(rs_module.camera_repository, "get_all", no_cameras)
    monkeypatch.setattr(rs_module.pairs_repository, "get_as_tuples", no_pairs)
    monkeypatch.setattr(rs_module, "HttpDispatchGateway", lambda **kw: object())
    monkeypatch.setattr(rs_module, "InferenceEngine", FakeComponent)
    monkeypatch.setattr(rs_module, "PairManager", FakeComponent)
    monkeypatch.setattr(rs_module, "SingleDispatch", lambda *a, **k: object())
    monkeypatch.setattr(rs_module, "DispatchService", lambda *a, **k: object())
    monkeypatch.setattr(container, "bind_dispatch_gateway", lambda gw: None)
    monkeypatch.setattr(container, "bind_runtime", lambda *a, **k: None)
    monkeypatch.setattr(container, "unbind_runtime", lambda: None)
    return monkeypatch


def test_camera_failure_stops_inference_engine(patched):
    """Camera nổ sau khi inference đã chạy → inference phải được dọn."""
    patched.setattr(
        rs_module,
        "CameraManager",
        lambda **kw: FakeComponent(fail_on_start=True),
    )
    service = RuntimeService()

    with pytest.raises(RuntimeError):
        asyncio.run(service.start())

    inference = FakeComponent.instances[0]
    assert inference.started
    assert inference.stopped, "InferenceEngine bị bỏ lại → rò thread + VRAM"


def test_state_is_clean_after_failed_start(patched):
    patched.setattr(
        rs_module,
        "CameraManager",
        lambda **kw: FakeComponent(fail_on_start=True),
    )
    service = RuntimeService()

    with pytest.raises(RuntimeError):
        asyncio.run(service.start())

    assert service._components == {}
    assert service.status()["running"] is False


def test_retry_after_failure_does_not_leave_two_engines(patched):
    """
    Thử lại sau khi lỗi không được cộng dồn engine.

    Đây là hệ quả nặng nhất của bug cũ: mỗi lần reload thất bại chiếm thêm VRAM
    mà không bao giờ giải phóng.
    """
    patched.setattr(
        rs_module,
        "CameraManager",
        lambda **kw: FakeComponent(fail_on_start=True),
    )
    service = RuntimeService()

    for _ in range(3):
        with pytest.raises(RuntimeError):
            asyncio.run(service.start())

    engines = [c for c in FakeComponent.instances if c.started]
    alive = [c for c in engines if not c.stopped]
    assert alive == [], f"{len(alive)} component còn sống sau 3 lần lỗi"


def test_stop_after_failed_start_is_safe(patched):
    patched.setattr(
        rs_module,
        "CameraManager",
        lambda **kw: FakeComponent(fail_on_start=True),
    )
    service = RuntimeService()

    with pytest.raises(RuntimeError):
        asyncio.run(service.start())

    assert service.stop()["running"] is False  # không được raise


def test_successful_start_registers_and_stops_all(patched):
    patched.setattr(rs_module, "CameraManager", lambda **kw: FakeComponent())
    service = RuntimeService()

    assert asyncio.run(service.start())["running"] is True
    assert set(service._components) >= {
        "inference_engine",
        "camera_manager",
        "pair_manager",
        "state_manager",
    }

    service.stop()
    assert all(c.stopped for c in FakeComponent.instances if c.started)
    assert service._components == {}


def test_start_is_idempotent_while_running(patched):
    patched.setattr(rs_module, "CameraManager", lambda **kw: FakeComponent())
    service = RuntimeService()

    asyncio.run(service.start())
    count_before = len(FakeComponent.instances)
    asyncio.run(service.start())

    assert len(FakeComponent.instances) == count_before
    service.stop()


def test_bind_runtime_control_keeps_reload_usable_without_runtime():
    """
    Sau khi start lỗi, `/runtime/reload` phải còn gọi được — nếu container giữ
    port rỗng thì người vận hành buộc phải restart app mới thử lại.
    """
    service = RuntimeService()
    original = container.runtime_control
    try:
        container.bind_runtime_control(service)
        assert container.runtime_control is service
        assert container.get_runtime_status.execute().data["running"] is False
    finally:
        container.bind_runtime_control(original)
