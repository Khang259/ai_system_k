"""JPEG overlay ROI + bbox — CPU, không GPU."""
import pytest

pytest.importorskip("cv2")
pytest.importorskip("numpy")

import numpy as np

from infrastructure.vision.preview_draw import (
    draw_overlay,
    encode_jpeg,
    frame_to_bgr,
    overlay_meta,
)


def test_frame_to_bgr_chw():
    rgb = np.zeros((3, 48, 64), dtype=np.uint8)
    rgb[0] = 255
    bgr = frame_to_bgr(rgb)
    assert bgr.shape == (48, 64, 3)
    assert int(bgr[0, 0, 2]) == 255


def test_draw_overlay_roi_and_box():
    bgr = np.zeros((480, 640, 3), dtype=np.uint8)
    rois = [{"node_id": "start_1", "roi": [10, 20, 100, 80]}]
    dets = np.array([[30.0, 40.0, 90.0, 120.0, 0.87, 0.0]], dtype=np.float32)
    out = draw_overlay(bgr, dets, rois)
    assert out.shape == bgr.shape
    jpeg = encode_jpeg(out, quality=80)
    assert jpeg[:2] == b"\xff\xd8"
    assert len(jpeg) > 100


def test_overlay_meta_shape():
    rois = [{"node_id": "start_1", "roi": [10, 20, 100, 80]}]
    dets = np.array([[30.0, 40.0, 90.0, 120.0, 0.87, 0.0]], dtype=np.float32)
    meta = overlay_meta(dets, rois, ts=12.5, width=640, height=480)
    assert meta["w"] == 640 and meta["h"] == 480
    assert meta["ts"] == 12.5
    assert meta["rois"][0]["roi"] == [10, 20, 100, 80]
    assert meta["dets"][0]["cls"] == 0
    assert meta["dets"][0]["xyxy"][0] == 30.0
