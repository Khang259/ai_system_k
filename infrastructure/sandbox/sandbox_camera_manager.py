"""
Camera giả cho sandbox — không RTSP/decode/AI.

Node vẫn sinh từ ROI của camera trong Mongo (dùng lại CameraManager).
Mỗi tick (~ 1 frame) đẩy state mong muốn của từng ROI vào NodeState,
chỉ khi camera đang enabled và inference không pause — giống camera thật.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np

from infrastructure.vision.camera_manager import CameraManager
from utils.setup_log import setup_logger

logger = setup_logger("sandbox", "logs/sandbox/log")

NO_VIDEO = "Sandbox mode: không có video"


class SandboxCameraManager(CameraManager):
    def __init__(
        self,
        cameras_config,
        state_manager,
        inference_engine,
        tick_sec: float = 0.2,
    ):
        super().__init__(cameras_config, state_manager, inference_engine)
        self._tick_sec = tick_sec
        self._desired: Dict[str, bool] = {}
        self._desired_lock = threading.Lock()
        self._nodes_by_index: List[List[str]] = [
            [roi["node_id"] for roi in self._get_internal_rois(cam)]
            for cam in self.cameras_config or []
        ]
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Vòng đời ──────────────────────────────────────────────
    def start(self):
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="SandboxCameras")
        self._thread.start()
        logger.info(f"Sandbox cameras started — {len(self._node_id_to_cam)} nodes")

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Sandbox cameras stopped")

    def _run(self):
        while self._running.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("Sandbox tick lỗi")
            time.sleep(self._tick_sec)

    def tick(self) -> None:
        """Một frame: inference pause hoặc camera tắt → không có detection."""
        if self.inference_engine.is_paused():
            return
        with self._enabled_lock:
            enabled = list(self.enabled)
        with self._desired_lock:
            desired = dict(self._desired)
        for index, node_ids in enumerate(self._nodes_by_index):
            if not enabled[index]:
                continue
            for node_id in node_ids:
                self.state_manager.get_state_nodes(node_id, desired.get(node_id, False))

    # ── Điều khiển sandbox ────────────────────────────────────
    def set_node_state(self, node_id: str, detected: bool) -> bool:
        """False nếu node không thuộc ROI của camera nào."""
        if node_id not in self._node_id_to_cam:
            return False
        with self._desired_lock:
            self._desired[node_id] = bool(detected)
        return True

    def get_node_states(self) -> List[Dict[str, Any]]:
        with self._enabled_lock:
            enabled = list(self.enabled)
        with self._desired_lock:
            desired = dict(self._desired)
        items = []
        for index, node_ids in enumerate(self._nodes_by_index):
            camera_id = self.cameras_config[index].get("cameraId")
            for node_id in node_ids:
                items.append({
                    "nodeId": node_id,
                    "cameraId": camera_id,
                    "cameraEnabled": enabled[index],
                    "detected": desired.get(node_id, False),
                })
        return items

    # ── Override phần cần video thật ──────────────────────────
    def get_status(self):
        with self._enabled_lock:
            enabled = list(self.enabled)
        cameras = [
            {
                "cam_id": self._make_cam_id(i, cam),
                "cameraId": cam.get("cameraId"),
                "enabled": enabled[i],
                "streaming": enabled[i],
                "error": None,
            }
            for i, cam in enumerate(self.cameras_config or [])
        ]
        return {
            "total": len(cameras),
            "alive": len(cameras) if self._running.is_set() else 0,
            "enabled": sum(enabled),
            "streaming": sum(enabled),
            "cameras": cameras,
        }

    def get_preview_jpeg(self, camera_id: int, detect: bool):
        return None, NO_VIDEO, 409

    def get_preview_meta(self, camera_id: int):
        return None, NO_VIDEO, 409

    def get_rtsp_url(self, camera_id: int):
        return None

    def capture_for_node(self, node_id: str):
        """
        Placeholder RGB cho snapshot sandbox (không có RTSP/GPU frame).

        SnapshotFsStore chỉ cần frame numpy HWC uint8 — đủ để FE tích hợp
        get_image / get_by_order khi ENABLE_SNAPSHOTS=true.
        """
        if node_id not in self._node_id_to_cam:
            return None

        cam_id, _ = self._node_id_to_cam[node_id]
        # Ảnh giả 320×240 — xanh đậm + chữ node (vẽ ở save_pair qua overlay)
        h, w = 240, 320
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = (32, 64, 96)
        # Vạch nhận diện nhanh trên JPEG
        frame[0:8, :] = (0, 200, 80)
        return {
            "frame": frame,
            "event": None,
            "detections": None,
            "rois": [{"node_id": node_id, "roi": [10, 10, 100, 80]}],
            "detection_ts": time.time(),
            "cam_id": cam_id,
        }
