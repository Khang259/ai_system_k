"""Smoke trail chỉ ghi khi RUNTIME_MODE=sandbox."""
from __future__ import annotations

from infrastructure.sandbox import smoke_trail


def test_emit_noop_outside_sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(smoke_trail.settings, "RUNTIME_MODE", "real")
    # Không được ném lỗi; không phụ thuộc file log
    smoke_trail.emit("api", "start_all", enabled=1)


def test_emit_writes_when_sandbox(monkeypatch, caplog):
    monkeypatch.setattr(smoke_trail.settings, "RUNTIME_MODE", "sandbox")
    with caplog.at_level("INFO", logger="smoke_trail"):
        smoke_trail.emit(
            "system",
            "dispatch",
            seq=1,
            startNodeId="start_9000001",
            endNodeId="end_9000101",
        )
    assert any("dispatch" in r.message and "start_9000001" in r.message for r in caplog.records)


def test_node_runtime_view_empty_when_no_state():
    assert smoke_trail.node_runtime_view(None, "start_1") == {}
