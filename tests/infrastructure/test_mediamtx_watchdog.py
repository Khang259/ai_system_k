"""MediaMtxRunner watchdog — mock probe/spawn, không chạy MediaMTX thật."""
import time

import pytest

pytest.importorskip("httpx")

from infrastructure.webrtc import mediamtx_runner as mod
from infrastructure.webrtc.mediamtx_runner import MediaMtxRunner


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    """Backoff về 0 để test không phải chờ thật."""
    monkeypatch.setattr(mod, "_BACKOFF_START_SEC", 0.0)
    monkeypatch.setattr(mod, "_BACKOFF_CAP_SEC", 0.0)


def _runner(monkeypatch, probe_results, max_restarts=2):
    """
    probe_results: bool trả lần lượt mỗi lần _probe(); cạn thì giữ giá trị cuối.
    Lần probe đầu là của start(), các lần sau là của watchdog loop.
    """
    runner = MediaMtxRunner(
        bin_path="",
        yml_path="config/mediamtx.yml",
        api_url="http://127.0.0.1:9997",
        watchdog_sec=0.01,
        max_restarts=max_restarts,
    )
    calls = {"probe": 0, "spawn": 0}

    def fake_probe():
        idx = min(calls["probe"], len(probe_results) - 1)
        calls["probe"] += 1
        return probe_results[idx]

    def fake_spawn():
        calls["spawn"] += 1
        return True

    monkeypatch.setattr(runner, "_probe", fake_probe)
    monkeypatch.setattr(runner, "_spawn", fake_spawn)
    return runner, calls


def test_alive_never_restarts(monkeypatch):
    runner, calls = _runner(monkeypatch, [True])
    runner.start()
    time.sleep(0.1)
    runner.stop()

    assert calls["spawn"] == 0
    assert runner._restarts == 0


def test_restarts_when_owned_process_dies(monkeypatch):
    # probe: start() thấy sống → không spawn; loop sau đó thấy chết
    runner, calls = _runner(monkeypatch, [True, False])
    runner._proc = object()  # app là chủ tiến trình
    runner.start()
    time.sleep(0.15)
    runner.stop()

    assert calls["spawn"] >= 1
    assert runner._restarts >= 1


def test_gives_up_after_max_restarts(monkeypatch):
    runner, calls = _runner(monkeypatch, [True, False], max_restarts=2)
    runner._proc = object()
    runner.start()
    time.sleep(0.3)
    runner.stop()

    assert runner._gave_up is True
    # Chỉ restart tối đa max_restarts lần rồi dừng
    assert calls["spawn"] <= 2


def test_external_instance_is_not_respawned(monkeypatch):
    """MediaMTX chạy ngoài app chết → chỉ log, không tự bật bản của mình."""
    runner, calls = _runner(monkeypatch, [True, False])
    runner.start()  # probe True → external=True, _proc vẫn None
    assert runner._external is True
    time.sleep(0.1)
    runner.stop()

    assert calls["spawn"] == 0
    assert runner._restarts == 0


def test_recovery_resets_restart_counter(monkeypatch):
    # chết một nhịp rồi sống lại
    runner, _ = _runner(monkeypatch, [True, False, True])
    runner._proc = object()
    runner.start()
    time.sleep(0.2)
    runner.stop()

    assert runner._restarts == 0
    assert runner._gave_up is False


def test_stop_halts_watchdog_thread(monkeypatch):
    runner, _ = _runner(monkeypatch, [True])
    runner.start()
    assert runner._thread is not None

    runner.stop()
    assert runner._thread is None
    assert runner._stop_flag.is_set()


def test_watchdog_disabled_when_interval_zero(monkeypatch):
    runner, _ = _runner(monkeypatch, [True])
    runner.watchdog_sec = 0
    runner.start()

    assert runner._thread is None
    runner.stop()


def test_status_reports_fields(monkeypatch):
    runner, _ = _runner(monkeypatch, [True])
    st = runner.status()

    assert st["alive"] is True
    assert st["owned"] is False
    assert st["watchdog"] is True
