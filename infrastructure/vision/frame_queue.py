"""Ring-buffer frame queue cho InferenceEngine (CUDA frame refs + decode_event)."""
from __future__ import annotations

import queue
import threading
import time

from utils.setup_log import setup_logger

logger = setup_logger("inference_engine", "logs/inference_engine/log")


class PreAllocatedFrameQueue:
    """
    Ring buffer giữ frame CUDA + decode_event + cam_id.

    Không copy tensor lúc put (frame đã clone trên decode stream).
    Inference wait_event rồi mới đọc frame — tránh race và giữ overlap.
    """

    def __init__(self, max_size=500, height=480, width=640):
        self.max_size = max_size
        self.height = height
        self.width = width
        self.frames = [None] * max_size
        self.cam_ids = [None] * max_size
        self.events = [None] * max_size
        self.write_idx = 0
        self.read_idx = 0
        self.count = 0
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        logger.info(
            f"Frame queue (ring refs): {max_size} slots × {height}×{width}"
        )

    def put_nowait(self, frame, cam_id, decode_event=None):
        with self._lock:
            if self.count >= self.max_size:
                raise queue.Full("Queue is full")
            self.frames[self.write_idx] = frame
            self.cam_ids[self.write_idx] = cam_id
            self.events[self.write_idx] = decode_event
            self.write_idx = (self.write_idx + 1) % self.max_size
            self.count += 1
            self._not_empty.notify()

    def get(self, timeout=None):
        with self._not_empty:
            end_time = None if timeout is None else (time.time() + timeout)
            while self.count == 0:
                if timeout is not None:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        raise queue.Empty("Queue is empty")
                    if not self._not_empty.wait(timeout=remaining):
                        raise queue.Empty("Queue is empty")
                else:
                    self._not_empty.wait()
            return self._pop_locked()

    def get_nowait(self):
        with self._lock:
            if self.count == 0:
                raise queue.Empty("Queue is empty")
            return self._pop_locked()

    def _pop_locked(self):
        frame = self.frames[self.read_idx]
        cam_id = self.cam_ids[self.read_idx]
        event = self.events[self.read_idx]
        self.frames[self.read_idx] = None
        self.cam_ids[self.read_idx] = None
        self.events[self.read_idx] = None
        self.read_idx = (self.read_idx + 1) % self.max_size
        self.count -= 1
        self._not_full.notify()
        return frame, cam_id, event

    def qsize(self):
        with self._lock:
            return self.count

    def empty(self):
        with self._lock:
            return self.count == 0

    def full(self):
        with self._lock:
            return self.count >= self.max_size
