"""Filesystem snapshot store — lưu JPEG pair khi dispatch thành công."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from utils.setup_log import setup_logger

logger = setup_logger("snapshot_fs", "logs/snapshot_fs/log")


def _sanitize_for_filename(value: str) -> str:
    """Chuẩn hoá chuỗi để dùng làm tên file an toàn trên Windows."""
    value = value.replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


class SnapshotFsStore:
    """
    Snapshot store với pull model: chốt frame từ FrameProvider lúc dispatch.
    
    Ghi overlay JPEG + JSON sidecar. Không giữ buffer frame, không retry sleep.
    """
    
    def __init__(
        self,
        frame_provider,
        snapshot_dir: str = "snapshots",
        quality: int = 95,
    ):
        self.frame_provider = frame_provider
        self.snapshot_dir = snapshot_dir
        self.quality = max(0, min(int(quality), 100))
        self._lock = threading.Lock()
        self._count = 0

        os.makedirs(self.snapshot_dir, exist_ok=True)
        logger.info(
            f"SnapshotFsStore initialized - dir: {self.snapshot_dir}, quality: {self.quality}"
        )

    def capture_pair(
        self, start_point: str, end_point: str
    ) -> Optional[Dict[str, Any]]:
        """
        Chốt frame + metadata cho cả hai node TRƯỚC khi gửi ICS.
        
        Returns dict hoặc None nếu thiếu camera/frame. Dict chứa:
            {
                "start": {"frame": tensor, "event": Event, "detections": ..., ...},
                "end": {...},
            }
        """
        start_cap = self.frame_provider.capture_for_node(start_point)
        end_cap = self.frame_provider.capture_for_node(end_point)
        
        if start_cap is None:
            logger.info(f"No camera/frame for start node: {start_point}")
        if end_cap is None:
            logger.info(f"No camera/frame for end node: {end_point}")
        
        if start_cap is None and end_cap is None:
            return None
        
        return {"start": start_cap, "end": end_cap}

    def save_pair_snapshots(
        self,
        capture: Optional[Dict[str, Any]],
        start_point: str,
        end_point: str,
        order_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Ghi ảnh pair từ capture đã chốt TRƯỚC, SAU khi ICS trả thành công.
        
        Tải GPU→CPU, vẽ overlay, ghi JPEG + JSON sidecar.
        Format: {orderId}_{start}-{end}_{timestamp}.jpg + .json
        
        Returns: (start_path, end_path) hoặc (None, None) nếu không có capture.
        """
        if capture is None:
            return None, None
        
        start_cap = capture.get("start")
        end_cap = capture.get("end")
        
        if start_cap is None and end_cap is None:
            return None, None
        
        # Import tại đây để tránh lỗi khi torch không có
        try:
            from infrastructure.vision.preview_draw import (
                draw_overlay,
                frame_to_bgr,
                overlay_meta,
            )
        except ImportError as e:
            logger.error(f"Failed to import preview_draw: {e}")
            return None, None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_order_id = _sanitize_for_filename(order_id)
        
        try:
            frames_bgr = []
            metas = []
            
            for cap, node_id in [(start_cap, start_point), (end_cap, end_point)]:
                if cap is None:
                    frames_bgr.append(None)
                    metas.append(None)
                    continue
                
                # Đồng bộ decode event trước khi .cpu() (phòng vệ race)
                event = cap.get("event")
                if event is not None:
                    event.synchronize()
                
                # Tải frame GPU → CPU
                frame = cap["frame"]
                bgr = frame_to_bgr(frame)
                
                # Vẽ overlay
                detections = cap.get("detections")
                rois = cap.get("rois", [])
                bgr_overlay = draw_overlay(bgr, detections, rois)
                
                frames_bgr.append(bgr_overlay)
                
                # Metadata JSON
                detection_ts = cap.get("detection_ts", 0.0)
                detection_age = time.time() - detection_ts if detection_ts > 0 else 0.0
                meta = overlay_meta(
                    detections,
                    rois,
                    time.time(),
                    bgr.shape[1],  # width
                    bgr.shape[0],  # height
                )
                meta["detection_age"] = round(detection_age, 3)
                meta["node_id"] = node_id
                meta["cam_id"] = cap.get("cam_id")
                metas.append(meta)
            
            # Ghi file
            start_bgr, end_bgr = frames_bgr
            start_meta, end_meta = metas
            
            if start_bgr is not None and end_bgr is not None:
                # Cả hai có → ghép ngang
                combined = np.hstack([start_bgr, end_bgr])
                filename = f"{safe_order_id}_{start_point}-{end_point}_{timestamp}.jpg"
                path = os.path.join(self.snapshot_dir, filename)
                ok = cv2.imwrite(
                    path, combined, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
                )
                if ok:
                    with self._lock:
                        self._count += 1
                    logger.info(f"Saved pair snapshot: {filename}")
                    
                    # Ghi JSON sidecar
                    json_path = path.replace(".jpg", ".json")
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "order_id": order_id,
                                "start": start_meta,
                                "end": end_meta,
                            },
                            f,
                            indent=2,
                        )
                    
                    return path, path
                else:
                    logger.error(f"Failed to write snapshot: {path}")
            
            elif start_bgr is not None:
                # Chỉ có start
                filename = f"{safe_order_id}_{start_point}-{end_point}_{timestamp}.jpg"
                path = os.path.join(self.snapshot_dir, filename)
                ok = cv2.imwrite(
                    path, start_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
                )
                if ok:
                    with self._lock:
                        self._count += 1
                    logger.info(f"Saved snapshot (start only): {filename}")
                    
                    # Ghi JSON
                    json_path = path.replace(".jpg", ".json")
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {"order_id": order_id, "start": start_meta, "end": None},
                            f,
                            indent=2,
                        )
                    
                    return path, None
                else:
                    logger.error(f"Failed to write snapshot: {path}")
            
            elif end_bgr is not None:
                # Chỉ có end
                filename = f"{safe_order_id}_{start_point}-{end_point}_{timestamp}.jpg"
                path = os.path.join(self.snapshot_dir, filename)
                ok = cv2.imwrite(
                    path, end_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
                )
                if ok:
                    with self._lock:
                        self._count += 1
                    logger.info(f"Saved snapshot (end only): {filename}")
                    
                    # Ghi JSON
                    json_path = path.replace(".jpg", ".json")
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {"order_id": order_id, "start": None, "end": end_meta},
                            f,
                            indent=2,
                        )
                    
                    return None, path
                else:
                    logger.error(f"Failed to write snapshot: {path}")
        
        except Exception as e:
            logger.error(f"Error saving snapshots for orderId={order_id}: {e}")
        
        return None, None

    def get_snapshot_count(self) -> int:
        with self._lock:
            return self._count

    def cleanup_old_snapshots(self, keep_days: int = 7):
        """Xóa ảnh + JSON cũ hơn keep_days. Chưa có ai gọi — cần scheduler."""
        try:
            cutoff = datetime.now() - timedelta(days=keep_days)
            removed = 0

            for filename in os.listdir(self.snapshot_dir):
                if not (
                    filename.lower().endswith(".jpg")
                    or filename.lower().endswith(".json")
                ):
                    continue

                path = os.path.join(self.snapshot_dir, filename)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if mtime < cutoff:
                        os.remove(path)
                        removed += 1
                except Exception as e:
                    logger.warning(f"Failed to check/remove file {path}: {e}")

            if removed > 0:
                logger.info(
                    f"Cleanup old snapshots: removed {removed} files older than {keep_days} days"
                )
        except Exception as e:
            logger.error(f"Error during cleanup_old_snapshots: {e}")
