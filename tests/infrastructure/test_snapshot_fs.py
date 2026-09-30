"""
SnapshotFsStore — pull model qua FrameProvider.

Store tự đi lấy frame lúc dispatch (không còn update_frame push vào).
Test dùng numpy frame + fake provider nên không cần GPU/torch.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest


def test_storage_module_present():
    assert Path("infrastructure/storage/snapshot_fs.py").is_file()
    assert not Path("core/snapshot_manager.py").exists()


def test_core_pair_manager_removed_and_dispatch_present():
    assert not Path("core/pair_manager.py").exists()
    assert Path("infrastructure/dispatch/pair_manager.py").is_file()
    assert importlib.util.find_spec("infrastructure.dispatch.pair_manager") is not None


needs_cv2 = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None or importlib.util.find_spec("cv2") is None,
    reason="numpy/cv2 not installed in this environment",
)


class _FakeEvent:
    """CUDA event giả — chỉ ghi nhận store có gọi synchronize() hay không."""

    def __init__(self) -> None:
        self.synced = False

    def synchronize(self) -> None:
        self.synced = True


class _FakeFrameProvider:
    """CameraManager giả: trả frame numpy cho các node đã đăng ký."""

    def __init__(self, frames: dict) -> None:
        self._frames = frames
        self.events = {}

    def capture_for_node(self, node_id: str):
        frame = self._frames.get(node_id)
        if frame is None:
            return None
        event = _FakeEvent()
        self.events[node_id] = event
        return {
            "frame": frame,
            "event": event,
            "detections": None,
            "rois": [{"node_id": node_id, "roi": [0, 0, 2, 2]}],
            "detection_ts": 0.0,
            "cam_id": f"cam_of_{node_id}",
        }


def _store(tmp_path, frames, indexer=None):
    from infrastructure.storage.snapshot_fs import SnapshotFsStore

    provider = _FakeFrameProvider(frames)
    return (
        SnapshotFsStore(
            provider, snapshot_dir=str(tmp_path), quality=80, indexer=indexer
        ),
        provider,
    )

@needs_cv2
def test_capture_pair_returns_none_when_no_camera(tmp_path):
    store, _ = _store(tmp_path, {})
    assert store.capture_pair("start_1", "end_1") is None


@needs_cv2
def test_capture_pair_keeps_partial_when_only_start_has_frame(tmp_path):
    import numpy as np

    store, _ = _store(tmp_path, {"start_1": np.zeros((4, 4, 3), dtype=np.uint8)})
    capture = store.capture_pair("start_1", "end_1")

    assert capture is not None
    assert capture["start"] is not None
    assert capture["end"] is None


@needs_cv2
def test_save_pair_snapshots_noop_without_capture(tmp_path):
    store, _ = _store(tmp_path, {})
    assert store.save_pair_snapshots(None, "start_1", "end_1", "order-1") == (None, None)


@needs_cv2
def test_save_pair_snapshots_writes_combined_jpeg_and_json(tmp_path):
    import numpy as np

    frames = {
        "start_1": np.zeros((4, 4, 3), dtype=np.uint8),
        "end_1": np.ones((4, 4, 3), dtype=np.uint8) * 255,
    }
    store, provider = _store(tmp_path, frames)
    capture = store.capture_pair("start_1", "end_1")

    with patch(
        "infrastructure.storage.snapshot_fs.cv2.imwrite", return_value=True
    ) as imwrite:
        path_a, path_b = store.save_pair_snapshots(
            capture, "start_1", "end_1", "S-1-1-abc"
        )

    assert path_a is not None
    assert path_a == path_b
    assert "S-1-1-abc_start_1-end_1_" in Path(path_a).name
    assert path_a.endswith(".jpg")

    # Ảnh ghép ngang: 2 frame 4x4 → 4x8
    assert imwrite.call_count == 1
    assert imwrite.call_args[0][1].shape == (4, 8, 3)
    assert store.get_snapshot_count() == 1

    # Event của cả hai node phải được đồng bộ trước khi đọc frame
    assert provider.events["start_1"].synced
    assert provider.events["end_1"].synced

    # JSON sidecar đi kèm
    sidecar = Path(path_a.replace(".jpg", ".json"))
    assert sidecar.is_file()
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["order_id"] == "S-1-1-abc"
    assert meta["start"]["node_id"] == "start_1"
    assert meta["end"]["node_id"] == "end_1"
    assert "detection_age" in meta["start"]


@needs_cv2
def test_save_pair_snapshots_start_only_when_end_missing(tmp_path):
    import numpy as np

    store, _ = _store(tmp_path, {"start_1": np.zeros((2, 2, 3), dtype=np.uint8)})
    capture = store.capture_pair("start_1", "end_missing")

    with patch(
        "infrastructure.storage.snapshot_fs.cv2.imwrite", return_value=True
    ) as imwrite:
        path_a, path_b = store.save_pair_snapshots(
            capture, "start_1", "end_missing", "order:1"
        )

    assert path_a is not None
    assert path_b is None
    assert "order_1_" in Path(path_a).name
    assert imwrite.call_count == 1

    meta = json.loads(
        Path(path_a.replace(".jpg", ".json")).read_text(encoding="utf-8")
    )
    assert meta["end"] is None


@needs_cv2
def test_save_pair_snapshots_calls_indexer(tmp_path):
    import numpy as np

    class _Idx:
        def __init__(self):
            self.calls = []

        def record(self, **kwargs):
            self.calls.append(kwargs)

    idx = _Idx()
    frames = {
        "start_1": np.zeros((4, 4, 3), dtype=np.uint8),
        "end_1": np.ones((4, 4, 3), dtype=np.uint8) * 255,
    }
    store, _ = _store(tmp_path, frames, indexer=idx)
    capture = store.capture_pair("start_1", "end_1")

    with patch("infrastructure.storage.snapshot_fs.cv2.imwrite", return_value=True):
        path, _ = store.save_pair_snapshots(capture, "start_1", "end_1", "ord-9")

    assert len(idx.calls) == 2
    assert {c["node_id"] for c in idx.calls} == {"start_1", "end_1"}
    assert all(c["order_id"] == "ord-9" for c in idx.calls)
    assert all(c["image_path"] == path for c in idx.calls)
