import threading
import queue
from typing import Any, Dict, Optional

from config.settings import settings
from infrastructure.vision.camera_processor import CameraProcessor
from infrastructure.vision.preview_store import PreviewStore
from utils.setup_log import setup_logger

logger = setup_logger("camera_manager", "logs/camera_manager/log")


class CameraManager:
    def __init__(
        self,
        cameras_config,
        state_manager,
        inference_engine,
        camera_zones=None,
        api_client=None,
    ):
        self.cameras_config = cameras_config
        self.state_manager = state_manager
        self.inference_engine = inference_engine
        self.camera_zones = camera_zones or []
        self.api_client = api_client
        if not self.camera_zones and cameras_config:
            self.camera_zones = [
                str(cam.get("zone_id") or cam.get("area") or "").upper()
                for cam in cameras_config
            ]

        self.threads = []
        self.enabled = [False] * len(cameras_config)
        self._enabled_lock = threading.Lock()
        self.latest_frames = {}
        self._node_id_to_cam = {}
        self._by_public_id = {}
        self.preview_store = PreviewStore()
        self._rtsp_by_id = {}
        for cam in cameras_config or []:
            cid = cam.get("cameraId")
            if cid is not None:
                self._rtsp_by_id[int(cid)] = self._get_cam_url(cam)
        self._build_node_id_to_cam()

    def _get_cam_url(self, cam: dict) -> str:
        return cam.get("url") or cam.get("rtsp") or ""

    def _make_cam_id(self, index: int, cam: dict) -> str:
        camera_id = cam.get("cameraId")
        if camera_id is not None:
            return f"cam_{index}_{camera_id}"
        cam_url = self._get_cam_url(cam)
        parts = cam_url.split(".")
        suffix = parts[-2] if len(parts) >= 2 else index
        return f"cam_{index}_{suffix}"

    def _get_internal_rois(self, cam: dict):
        rois = cam.get("rois", [])
        if isinstance(rois, dict):
            internal = []
            for roi_key, roi_val in rois.items():
                if isinstance(roi_val, dict):
                    coords = roi_val.get("roi")
                    is_start = bool(roi_val.get("start"))
                    is_end = bool(roi_val.get("end"))
                else:
                    coords = roi_val
                    is_start = False
                    is_end = False

                if not coords or len(coords) < 4:
                    continue

                roi_key_str = str(roi_key)
                if roi_key_str.startswith("start_") or roi_key_str.startswith("end_"):
                    node_id = roi_key_str
                else:
                    if is_start:
                        node_id = f"start_{roi_key_str}"
                    elif is_end:
                        node_id = f"end_{roi_key_str}"
                    else:
                        continue

                internal.append({"node_id": node_id, "roi": coords})
            return internal

        return rois or []

    def _build_node_id_to_cam(self):
        for i, cam in enumerate(self.cameras_config):
            cam_id = self._make_cam_id(i, cam)
            for roi_dict in self._get_internal_rois(cam):
                node_id = roi_dict.get("node_id")
                if node_id and node_id not in self._node_id_to_cam:
                    self._node_id_to_cam[node_id] = (cam_id, i)

    def start(self):
        for i, cam in enumerate(self.cameras_config):
            cam_url = self._get_cam_url(cam)
            cam_id = self._make_cam_id(i, cam)

            result_queue = queue.Queue(maxsize=10)
            self.inference_engine.register_camera(cam_id, result_queue)

            rois_internal = self._get_internal_rois(cam)
            thread = CameraProcessor(
                cam_url,
                rois_internal,
                self.state_manager,
                self.inference_engine,
                result_queue,
                cam_id,
                enabled_ref=self.enabled,
                camera_index=i,
                latest_frames_ref=self.latest_frames,
                api_client=self.api_client,
                public_camera_id=cam.get("cameraId"),
                preview_store=self.preview_store,
            )
            self.threads.append(thread)
            public_id = cam.get("cameraId")
            if public_id is not None:
                self._by_public_id[int(public_id)] = thread
            thread.start()

        logger.info(f"All {len(self.threads)} camera threads started")

    def stop(self):
        logger.info("Stopping all camera threads...")
        # Clear latest frames khi stop để không giữ tensor GPU cũ
        self.latest_frames.clear()
        for thread in self.threads:
            if thread.is_alive():
                thread.running = False
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        alive_count = sum(1 for t in self.threads if t.is_alive())
        if alive_count > 0:
            logger.warning(f"{alive_count} camera threads still alive after shutdown")
        else:
            logger.info("All camera threads stopped successfully")

    def set_camera_enabled(self, index: int, on: bool):
        with self._enabled_lock:
            if 0 <= index < len(self.enabled):
                self.enabled[index] = on

    def set_camera_enabled_by_id(self, camera_id: int, on: bool) -> bool:
        """Bật/tắt theo cameraId Mongo. False nếu camera không có trong runtime."""
        cam = int(camera_id)
        for i, cfg in enumerate(self.cameras_config or []):
            if cfg.get("cameraId") == cam:
                self.set_camera_enabled(i, on)
                return True
        return False

    def set_zone_enabled(self, zone: str, on: bool):
        with self._enabled_lock:
            for i, z in enumerate(self.camera_zones):
                if i < len(self.enabled) and z == zone:
                    self.enabled[i] = on

    def start_all_cameras(self):
        with self._enabled_lock:
            for i in range(len(self.enabled)):
                self.enabled[i] = True
        logger.info("All cameras enabled")

    def stop_all_cameras(self):
        with self._enabled_lock:
            for i in range(len(self.enabled)):
                self.enabled[i] = False
        logger.info("All cameras disabled")

    def get_rtsp_url(self, camera_id: int):
        url = (self._rtsp_by_id.get(int(camera_id)) or "").strip()
        return url or None

    def get_preview_jpeg(self, camera_id: int, detect: bool):
        """(jpeg_bytes|None, error|None, http_status)."""
        cam = int(camera_id)
        thread = self._by_public_id.get(cam)
        if thread is None:
            return None, "Camera not found", 404
        if not thread._is_enabled():
            return None, "Camera disabled. POST /cameras/start-all first.", 409
        if not getattr(thread, "streaming", False):
            err = getattr(thread, "last_error", None) or "waiting for RTSP"
            return None, f"Camera not streaming: {err}", 409

        self.preview_store.watch(cam, settings.PREVIEW_WATCH_SEC)
        jpeg = self.preview_store.get_wait(
            cam, detect=detect, timeout=settings.PREVIEW_WAIT_SEC
        )
        if jpeg is None:
            return None, "No preview yet", 503
        return jpeg, None, 200

    def get_preview_meta(self, camera_id: int):
        """(meta dict|None, error|None, http_status). F5 canvas overlay."""
        cam = int(camera_id)
        thread = self._by_public_id.get(cam)
        if thread is None:
            return None, "Camera not found", 404
        if not thread._is_enabled():
            return None, "Camera disabled. POST /cameras/start-all first.", 409
        if not getattr(thread, "streaming", False):
            err = getattr(thread, "last_error", None) or "waiting for RTSP"
            return None, f"Camera not streaming: {err}", 409

        self.preview_store.watch(cam, settings.PREVIEW_WATCH_SEC)
        meta = self.preview_store.get_wait_meta(
            cam, timeout=settings.PREVIEW_WAIT_SEC
        )
        if meta is None:
            return None, "No preview meta yet", 503
        return meta, None, 200

    def get_cam_id_for_node(self, node_id: str):
        info = self._node_id_to_cam.get(node_id)
        return info[0] if info else None

    def get_status(self):
        with self._enabled_lock:
            enabled_count = sum(1 for e in self.enabled if e)
            enabled_copy = list(self.enabled)
        cameras = []
        streaming_count = 0
        for i, thread in enumerate(self.threads):
            streaming = bool(getattr(thread, "streaming", False))
            if streaming:
                streaming_count += 1
            public_id = getattr(thread, "public_camera_id", None)
            if public_id is None and i < len(self.cameras_config or []):
                public_id = (self.cameras_config or [])[i].get("cameraId")
            cameras.append(
                {
                    "cam_id": getattr(thread, "cam_id", f"cam_{i}"),
                    "cameraId": public_id,
                    "enabled": enabled_copy[i] if i < len(enabled_copy) else False,
                    "streaming": streaming,
                    "error": getattr(thread, "last_error", None),
                }
            )
        return {
            "total": len(self.threads),
            "alive": sum(1 for t in self.threads if t.is_alive()),
            "enabled": enabled_count,
            "streaming": streaming_count,
            "cameras": cameras,
        }

    def capture_for_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy frame + metadata mới nhất cho snapshot (implement FrameProvider).
        
        Returns dict với frame (CUDA), event, detections, rois, detection_ts, cam_id
        hoặc None nếu node không tìm thấy hoặc camera chưa có frame.
        """
        # Tìm camera từ node_id
        info = self._node_id_to_cam.get(node_id)
        if info is None:
            return None
        
        cam_id, cam_index = info
        
        # Lấy frame + event từ latest_frames (đọc một lần vào local variable)
        frame_data = self.latest_frames.get(cam_id)
        if frame_data is None:
            return None
        
        frame, event = frame_data
        
        # Lấy metadata từ thread
        if cam_index >= len(self.threads):
            return None
        
        thread = self.threads[cam_index]
        meta = thread.get_latest_capture()
        if meta is None:
            return None
        
        # Gộp frame + event + metadata
        return {
            "frame": frame,
            "event": event,
            **meta,
        }
