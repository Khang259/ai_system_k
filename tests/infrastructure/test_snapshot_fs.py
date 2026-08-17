"""SnapshotFsStore — path layout luôn chạy; write JPEG cần numpy/cv2."""
from __future__ import annotations

import importlib.util
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


@pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None or importlib.util.find_spec("cv2") is None,
    reason="numpy/cv2 not installed in this environment",
)
def test_save_pair_snapshots_writes_combined_jpeg(tmp_path):
    import numpy as np
    from infrastructure.storage.snapshot_fs import SnapshotFsStore

    store = SnapshotFsStore(snapshot_dir=str(tmp_path), quality=80)
    start = np.zeros((4, 4, 3), dtype=np.uint8)
    end = np.ones((4, 4, 3), dtype=np.uint8) * 255
    store.update_frame("start_1", start)
    store.update_frame("end_1", end)

    with patch("infrastructure.storage.snapshot_fs.cv2.imwrite", return_value=True) as imwrite:
        path_a, path_b = store.save_pair_snapshots("start_1", "end_1", "S-1-1-abc")

    assert path_a is not None
    assert path_a == path_b
    assert "S-1-1-abc_start_1-end_1_" in Path(path_a).name
    assert path_a.endswith(".jpg")
    assert imwrite.call_count == 1
    written = imwrite.call_args[0][1]
    assert written.shape == (4, 8, 3)
    assert store.get_snapshot_count() == 1


@pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None or importlib.util.find_spec("cv2") is None,
    reason="numpy/cv2 not installed in this environment",
)
def test_save_pair_snapshots_start_only_when_end_missing(tmp_path):
    import numpy as np
    from infrastructure.storage.snapshot_fs import SnapshotFsStore

    store = SnapshotFsStore(snapshot_dir=str(tmp_path), quality=80)
    store.update_frame("start_1", np.zeros((2, 2, 3), dtype=np.uint8))

    with patch("infrastructure.storage.snapshot_fs.time.sleep"), patch(
        "infrastructure.storage.snapshot_fs.cv2.imwrite", return_value=True
    ) as imwrite:
        path_a, path_b = store.save_pair_snapshots("start_1", "end_missing", "order:1")

    assert path_a is not None
    assert path_b is None
    assert "order_1_" in Path(path_a).name
    assert imwrite.call_count == 1
