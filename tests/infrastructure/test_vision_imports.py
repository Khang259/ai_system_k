"""Smoke import vision modules — không cần GPU / RTSP / model thật."""
import importlib
from pathlib import Path

import pytest

VISION_FILES = (
    "detection.py",
    "gpu_video_decoder.py",
    "gpu_frame.py",
    "cuda_decode_pool.py",
    "annexb_pipe.py",
    "inference_engine.py",
    "trt_yolo_engine.py",
    "camera_processor.py",
    "camera_manager.py",
    "preview_store.py",
    "preview_draw.py",
    "__init__.py",
)

REMOVED_CORE_FILES = (
    "detection.py",
    "gpu_video_decoder.py",
    "inference_engine.py",
    "camera_processor.py",
    "camera_manager.py",
)


def test_vision_files_present():
    base = Path("infrastructure/vision")
    for name in VISION_FILES:
        assert (base / name).is_file(), f"missing {base / name}"


def test_core_vision_files_removed():
    for name in REMOVED_CORE_FILES:
        assert not (Path("core") / name).exists(), f"core/{name} should be removed"


@pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None
    or importlib.util.find_spec("torch") is None
    or importlib.util.find_spec("ultralytics") is None,
    reason="vision runtime deps not installed in this environment",
)
def test_vision_package_exports():
    from infrastructure.vision import CameraManager, InferenceEngine

    assert CameraManager is not None
    assert InferenceEngine is not None


@pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None
    or importlib.util.find_spec("torch") is None
    or importlib.util.find_spec("ultralytics") is None,
    reason="vision runtime deps not installed in this environment",
)
def test_vision_modules_importable():
    modules = [
        "infrastructure.vision.detection",
        "infrastructure.vision.gpu_video_decoder",
        "infrastructure.vision.camera_processor",
        "infrastructure.vision.camera_manager",
    ]
    for name in modules:
        mod = importlib.import_module(name)
        assert mod is not None
