import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor
from infrastructure.vision.detection import has_object_in_roi, has_object_in_rois_batch
from infrastructure.vision.preview_draw import (
    draw_overlay,
    encode_jpeg,
    frame_to_bgr,
    overlay_meta,
)
from config.settings import settings
from infrastructure.vision.gpu_video_decoder import GPUVideoDecoder
from utils.setup_log import setup_logger

logger = setup_logger("camera_processor", "logs/camera_processor/log")


class CameraProcessor(threading.Thread):
    def __init__(
        self,
        rtsp,
        rois,
        state_manager,
        inference_engine,
        result_queue,
        cam_id,
        enabled_ref=None,
        camera_index=0,
        latest_frames_ref=None,
        api_client=None,
        public_camera_id=None,
        preview_store=None,
    ):
        super().__init__()
        self.rtsp = rtsp
        self.rois = rois
        self.state_manager = state_manager
        self.inference_engine = inference_engine
        self.result_queue = result_queue
        self.cam_id = cam_id
        self.enabled_ref = enabled_ref if enabled_ref is not None else []
        self.camera_index = camera_index
        self.latest_frames_ref = latest_frames_ref if latest_frames_ref is not None else {}
        self.api_client = api_client
        self.public_camera_id = public_camera_id
        self.preview_store = preview_store
        self._last_preview_ts = 0.0
        self.running = True
        self.streaming = False
        self.last_error = None
        self.window_name = f"Camera {rtsp.split('/')[-1]}"
        
        # Sticky detections cache - giữ bbox ổn định trên UI
        self._last_detections = None           # Detection cuối cùng
        self._last_detections_ts = 0.0         # Timestamp của detection
        self.sticky_ttl_sec = 0.5              # TTL: giữ detection trong 0.5s
        
        # Async ROI processing - không block camera thread
        self.roi_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix=f"ROI-{cam_id}"
        )
        self._pending_roi_jobs = 0  # Track số job đang chạy

    def _is_enabled(self):
        if self.camera_index < len(self.enabled_ref):
            return self.enabled_ref[self.camera_index]
        return True

    def _publish_preview(self, frame, detections=None):
        if self.preview_store is None or self.public_camera_id is None:
            return
        if not self.preview_store.is_watched(self.public_camera_id):
            return
        now = time.monotonic()
        if now - self._last_preview_ts < settings.PREVIEW_INTERVAL_SEC:
            return
        self._last_preview_ts = now
        try:
            bgr = frame_to_bgr(frame)
            raw = encode_jpeg(bgr, settings.PREVIEW_JPEG_QUALITY)
            detect_jpeg = encode_jpeg(
                draw_overlay(bgr, detections, self.rois),
                settings.PREVIEW_JPEG_QUALITY,
            )
            
            # Tính tuổi của detection (để frontend biết sticky hay fresh)
            detection_age = 0.0
            if detections is not None and self._last_detections_ts > 0:
                detection_age = now - self._last_detections_ts
            
            meta = overlay_meta(
                detections,
                self.rois,
                time.time(),
                settings.MODEL_WIDTH,
                settings.MODEL_HEIGHT,
            )
            meta["detection_age"] = round(detection_age, 3)  # Thêm age cho frontend
            
            self.preview_store.put(
                self.public_camera_id, raw=raw, detect=detect_jpeg, meta=meta
            )
        except Exception as e:
            logger.warning(f"Preview encode failed {self.cam_id}: {e}")
    
    def _process_rois_async(self, detections, rois_snapshot, cam_id):
        """
        Xử lý ROI trong background thread - KHÔNG BLOCK camera thread.

        Args:
            detections: GPU tensor (N,6) từ nms_ready — giữ trên GPU, không
                round-trip qua CPU vì has_object_in_rois_batch tính trên GPU
            rois_snapshot: list of ROI dicts (copy từ self.rois)
            cam_id: camera ID
        """
        try:
            # Batch ROI check - chạy trong background, không block camera thread
            roi_results = has_object_in_rois_batch(detections, rois_snapshot, use_gpu=True)
            
            # Post detection results
            for has_obj, coverage, node_id in roi_results:
                if self.api_client:
                    self.api_client.post_detection(cam_id, node_id, has_obj, coverage)
                elif self.state_manager:
                    self.state_manager.get_state_nodes(node_id, has_obj)
            
        except Exception as e:
            logger.error(f"Async ROI processing error cam {cam_id}: {e}")
        finally:
            # Decrease pending job counter
            self._pending_roi_jobs = max(0, self._pending_roi_jobs - 1)

    def run(self):
        cap = None
        loop_count = 0
        slow_loop_count = 0

        while self.running:
            loop_start = time.monotonic()
            loop_count += 1
            
            # Khởi tạo timing variables
            t_read = t_put = t_get = t_preview = t_roi = 0.0
            
            if not self._is_enabled():
                self.streaming = False
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                time.sleep(1)
                continue

            if cap is None or not cap.isOpened():
                cap = GPUVideoDecoder(
                    self.rtsp,
                    width=settings.MODEL_WIDTH,
                    height=settings.MODEL_HEIGHT,
                    camera_index=self.camera_index,
                )
                if not cap.isOpened():
                    self.streaming = False
                    self.last_error = "Cannot open RTSP"
                    logger.error(f"Cannot open RTSP: {self.rtsp}")
                    time.sleep(2)
                    continue
                logger.info(f"Waiting for first frame from {self.rtsp}...")
                if not cap.wait_ready(timeout=settings.DECODE_WAIT_FIRST_FRAME_SEC):
                    self.streaming = False
                    self.last_error = "Timeout waiting for first frame"
                    logger.error(f"Timeout waiting for first frame from {self.rtsp}")
                    cap.release()
                    cap = None
                    time.sleep(2)
                    continue
                self.streaming = True
                self.last_error = None

            t_read_start = time.monotonic()
            ret, frame, decode_event = cap.read()
            t_read = time.monotonic() - t_read_start
            
            if not ret:
                if not cap.isOpened():
                    self.streaming = False
                    self.last_error = "Lost stream"
                    logger.warning(f"Lost stream from {self.rtsp} - try reconnect...")
                    cap.release()
                    cap = None
                    time.sleep(1)
                else:
                    time.sleep(0.005)
                continue

            # Lưu frame + event mới nhất cho snapshot (tham chiếu GPU, không copy)
            if self.latest_frames_ref is not None:
                self.latest_frames_ref[self.cam_id] = (frame, decode_event)

            # PHƯƠNG ÁN B: Push frame ngay, không đợi kết quả inference
            # QUEUE SHARDING: Truyền camera_index để route vào đúng shard
            t_put_start = time.monotonic()
            self.inference_engine.put_frame_with_drop(
                frame, self.cam_id, decode_event, camera_index=self.camera_index
            )
            t_put = time.monotonic() - t_put_start

            paused = getattr(self.inference_engine, "_paused", None)
            if paused is not None and paused.is_set():
                self._publish_preview(frame)
                time.sleep(0.03)
                continue

            # PHƯƠNG ÁN B: Non-blocking get kết quả, không chờ đợi
            t_get_start = time.monotonic()
            detections = None
            try:
                detections = self.result_queue.get_nowait()
            except queue.Empty:
                pass
            t_get = time.monotonic() - t_get_start

            # Sticky detections: Cập nhật cache nếu có detection mới
            if detections is not None:
                self._last_detections = detections
                self._last_detections_ts = time.monotonic()

            # Sticky detections: Dùng cache cũ nếu không có detection mới và chưa hết TTL
            display_detections = detections
            if display_detections is None and self._last_detections is not None:
                now = time.monotonic()
                if now - self._last_detections_ts < self.sticky_ttl_sec:
                    display_detections = self._last_detections

            # Publish preview với sticky detections (cho UI mượt)
            t_preview_start = time.monotonic()
            self._publish_preview(frame, display_detections)
            t_preview = time.monotonic() - t_preview_start

            # ASYNC ROI: Submit job vào thread pool - KHÔNG BLOCK camera thread
            t_roi_submit = 0.0
            if detections is not None and len(self.rois) > 0:
                t_roi_start = time.monotonic()
                
                # Giữ nguyên GPU tensor — has_object_in_rois_batch tính trên GPU.
                # Không cần copy phòng vệ: nms_ready trả tensor mới (boolean
                # indexing luôn cấp bộ nhớ riêng) nên batch sau không ghi đè.
                
                # Snapshot rois list để tránh concurrent modification
                rois_snapshot = list(self.rois)
                
                # Submit job - NON-BLOCKING!
                self._pending_roi_jobs += 1
                future = self.roi_executor.submit(
                    self._process_rois_async,
                    detections,
                    rois_snapshot,
                    self.cam_id
                )
                # ✅ KHÔNG GỌI future.result() → camera thread tiếp tục ngay!
                
                t_roi_submit = time.monotonic() - t_roi_start

            # PHƯƠNG ÁN B: Rate limiting - tránh busy-loop với mock video
            time.sleep(0.005)
            
            # Timing measurement và logging
            loop_time = time.monotonic() - loop_start
            if loop_time > 0.05:  # >50ms = chậm
                slow_loop_count += 1
                logger.warning(
                    f"Slow loop cam {self.cam_id}: {loop_time*1000:.1f}ms "
                    f"(read={t_read*1000:.1f}ms, put={t_put*1000:.1f}ms, "
                    f"get={t_get*1000:.1f}ms, preview={t_preview*1000:.1f}ms, "
                    f"roi_submit={t_roi_submit*1000:.1f}ms, pending_jobs={self._pending_roi_jobs}) "
                    f"slow_rate={slow_loop_count}/{loop_count}"
                )
            
            # Log định kỳ mỗi 300 loops (~50s @ 6fps) để track average
            if loop_count % 300 == 0:
                logger.info(
                    f"Cam {self.cam_id} performance: "
                    f"{loop_count} loops, {slow_loop_count} slow ({slow_loop_count*100/loop_count:.1f}%), "
                    f"pending_roi_jobs={self._pending_roi_jobs}"
                )

        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        
        # Cleanup ROI thread pool
        try:
            self.roi_executor.shutdown(wait=True, cancel_futures=False)
            logger.info(f"ROI executor shutdown for {self.cam_id}")
        except Exception as e:
            logger.warning(f"ROI executor shutdown error {self.cam_id}: {e}")

    def get_latest_capture(self) -> Optional[Dict[str, Any]]:
        """
        Trả về frame + metadata mới nhất cho snapshot.
        
        Gọi từ dispatch thread, không block camera thread.
        """
        if self._last_detections is None:
            return None
        
        return {
            "detections": self._last_detections,
            "detection_ts": self._last_detections_ts,
            "rois": list(self.rois),  # copy để tránh concurrent modification
            "cam_id": self.cam_id,
        }
