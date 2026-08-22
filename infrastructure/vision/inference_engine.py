"""Central inference: TRT multi-context + CUDA stream/event + optional PyTorch profiler."""
import queue
import threading
import time
from collections import deque

import torch
from torch.profiler import ProfilerActivity, profile, record_function

from infrastructure.vision.trt_yolo_engine import TrtYoloEngine
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


class InferenceEngine(threading.Thread):
    """Batch TRT inference: decode_event → wait → copy → execute_async_v3 → NMS → distribute."""

    def __init__(
        self,
        model_path,
        max_queue_size,
        max_batch_size,
        batch_timeout,
        num_streams,
        initial_paused: bool = False,
        use_preallocated_queue: bool = True,
        height: int = 480,
        width: int = 640,
        enable_profiler: bool = False,
        profiler_output: str = "trace.json",
        profiler_batches: int = 200,
        num_shards: int = 4,
    ):
        super().__init__(daemon=True, name="InferenceEngine")

        self.model_path = model_path
        self.max_queue_size = max_queue_size
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self.num_streams = max(1, int(num_streams))
        self.height = height
        self.width = width
        self.imgsz = (height, width)
        self.num_shards = max(1, int(num_shards))

        self._enable_profiler = bool(enable_profiler)
        self._profiler_output = profiler_output
        self._profiler_batches = max(1, int(profiler_batches))
        self._profiler_ctx = None
        self._batch_count = 0

        # QUEUE SHARDING: Chia 1 queue thành N shards để giảm lock contention
        if use_preallocated_queue:
            shard_size = max(1, max_queue_size // self.num_shards)
            self.shared_queues = [
                PreAllocatedFrameQueue(
                    max_size=shard_size, height=height, width=width
                )
                for _ in range(self.num_shards)
            ]
            logger.info(
                f"Using {self.num_shards} sharded ring-ref queues "
                f"({shard_size} slots each, {max_queue_size} total)"
            )
            # Backward compatibility: shared_queue points to first shard
            self.shared_queue = self.shared_queues[0]
        else:
            shard_size = max(1, max_queue_size // self.num_shards)
            self.shared_queues = [
                queue.Queue(maxsize=shard_size) for _ in range(self.num_shards)
            ]
            logger.info(
                f"Using {self.num_shards} sharded standard queues "
                f"({shard_size} slots each)"
            )
            self.shared_queue = self.shared_queues[0]

        self.result_queues = {}
        self.pending_batches = deque(maxlen=self.num_streams * 2)
        self.running = False
        self.engine = None
        self._slot_idx = 0
        self._shard_idx = 0  # Round-robin polling across shards
        self._paused = threading.Event()
        if initial_paused:
            self._paused.set()
        self._model_ready = threading.Event()
        self._load_done = threading.Event()
        self._load_error = None

    def pause(self) -> None:
        self._paused.set()
        logger.info("InferenceEngine paused")

    def resume(self) -> None:
        self._paused.clear()
        logger.info("InferenceEngine resumed")

    def is_model_loaded(self) -> bool:
        return self._model_ready.is_set()

    def load_error(self):
        return self._load_error

    def wait_model_ready(self, timeout: float) -> bool:
        self._load_done.wait(timeout)
        return self._model_ready.is_set()

    def register_camera(self, cam_id, result_queue):
        self.result_queues[cam_id] = result_queue

    def put_frame_with_drop(self, frame, cam_id, decode_event=None, camera_index=0):
        """
        Nhận frame CUDA + decode_event. Queue full → drop oldest.
        
        QUEUE SHARDING: Route frame vào shard dựa trên camera_index để giảm lock contention.
        Camera i → shard (i % num_shards)
        """
        shard_idx = camera_index % self.num_shards
        target_queue = self.shared_queues[shard_idx]
        
        try:
            if isinstance(target_queue, PreAllocatedFrameQueue):
                target_queue.put_nowait(frame, cam_id, decode_event)
            else:
                target_queue.put_nowait((frame, cam_id, decode_event))
        except queue.Full:
            try:
                target_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                if isinstance(target_queue, PreAllocatedFrameQueue):
                    target_queue.put_nowait(frame, cam_id, decode_event)
                else:
                    target_queue.put_nowait((frame, cam_id, decode_event))
            except queue.Full:
                pass

    def _pop_one(self, timeout):
        """
        QUEUE SHARDING: Poll round-robin từ các shards để balance load.
        """
        # Try all shards round-robin, starting from current shard_idx
        for offset in range(self.num_shards):
            shard_idx = (self._shard_idx + offset) % self.num_shards
            target_queue = self.shared_queues[shard_idx]
            
            try:
                # Use short timeout for non-first shards to avoid blocking
                shard_timeout = timeout if offset == 0 else 0.001
                item = target_queue.get(timeout=shard_timeout)
                
                # Update shard index for next poll (round-robin)
                self._shard_idx = (shard_idx + 1) % self.num_shards
                
                if isinstance(target_queue, PreAllocatedFrameQueue):
                    return item
                if len(item) == 3:
                    return item
                frame, cam_id = item
                return frame, cam_id, None
            except queue.Empty:
                continue
        
        # All shards empty
        raise queue.Empty("All shards empty")

    def _collect_batch(self):
        batch = []
        cam_ids = []
        ready_events = []
        start_time = time.time()

        while len(batch) < self.max_batch_size:
            timeout = self.batch_timeout - (time.time() - start_time)
            if timeout <= 0:
                break
            try:
                frame, cam_id, decode_event = self._pop_one(timeout)
                batch.append(frame)
                cam_ids.append(cam_id)
                ready_events.append(decode_event)
            except queue.Empty:
                break

        return batch, cam_ids, ready_events

    def _load_model(self):
        try:
            if not torch.cuda.is_initialized():
                torch.cuda.init()
            self.engine = TrtYoloEngine(
                engine_path=self.model_path,
                max_batch=self.max_batch_size,
                height=self.height,
                width=self.width,
                num_contexts=self.num_streams,
                device="cuda",
            )
            free_b, total_b = torch.cuda.mem_get_info()
            logger.info(
                f"TRT loaded contexts={self.num_streams} "
                f"GPU free={free_b / 1e9:.2f}/{total_b / 1e9:.2f} GB"
            )
            self._model_ready.set()
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"Failed to load TRT engine: {e}")
            raise
        finally:
            self._load_done.set()

    def _slot_busy(self, slot_idx: int) -> bool:
        return any(p["slot_idx"] == slot_idx for p in self.pending_batches)

    def _pick_free_slot(self):
        for offset in range(self.num_streams):
            idx = (self._slot_idx + offset) % self.num_streams
            if not self._slot_busy(idx):
                return idx
        return None

    def _async_inference(self, frames_batch, ready_events, slot_idx):
        slot = self.engine.slots[slot_idx]
        stream = slot.stream

        with torch.cuda.stream(stream):
            for ev in ready_events:
                if ev is not None:
                    stream.wait_event(ev)

            with record_function(f"trt_copy_batch_s{slot_idx}"):
                batch_size = self.engine.copy_batch(slot_idx, frames_batch)

            with record_function(f"trt_infer_async_s{slot_idx}"):
                event, batch_size = self.engine.infer_async(slot_idx, batch_size)

        return batch_size, event

    def _distribute_results(self, results, cam_ids):
        for detection, cam_id in zip(results, cam_ids):
            if cam_id not in self.result_queues:
                logger.warning(f"Camera {cam_id} not registered")
                continue
            try:
                self.result_queues[cam_id].put_nowait(detection)
            except queue.Full:
                try:
                    self.result_queues[cam_id].get_nowait()
                    self.result_queues[cam_id].put_nowait(detection)
                except (queue.Empty, queue.Full):
                    logger.warning(f"Failed to deliver result to {cam_id}")

    def _poll_pending(self):
        completed = []
        for i, batch_info in enumerate(self.pending_batches):
            if not batch_info["event"].query():
                continue
            results = self.engine.nms_ready(
                batch_info["slot_idx"],
                batch_info["batch_size"],
                conf=0.3,
                max_det=15,
            )
            self._distribute_results(results, batch_info["cam_ids"])
            completed.append(i)
        for i in reversed(completed):
            del self.pending_batches[i]

    def _start_profiler(self):
        if not self._enable_profiler:
            return
        self._profiler_ctx = profile(
            activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
            record_shapes=False,
            with_stack=False,
        )
        self._profiler_ctx.__enter__()
        self._batch_count = 0
        logger.info(
            f"PyTorch Profiler started — capture {self._profiler_batches} batches {self._profiler_output}"
        )

    def _stop_profiler(self):
        if self._profiler_ctx is None:
            return
        try:
            self._profiler_ctx.__exit__(None, None, None)
            self._profiler_ctx.export_chrome_trace(self._profiler_output)
            logger.info(f"PyTorch Profiler trace saved {self._profiler_output}")
        except Exception as e:
            logger.warning(f"Profiler stop/export failed: {e}")
        self._profiler_ctx = None

    def run(self):
        self.running = True
        try:
            self._load_model()
        except Exception:
            return

        self._start_profiler()

        while self.running:
            try:
                if self._paused.is_set():
                    self._poll_pending()
                    time.sleep(0.05)
                    continue

                self._poll_pending()

                batch_frames, cam_ids, ready_events = self._collect_batch()
                if len(batch_frames) == 0:
                    if len(self.pending_batches) == 0:
                        time.sleep(0.1)
                    continue

                slot_idx = self._pick_free_slot()
                if slot_idx is None:
                    oldest = self.pending_batches[0]
                    oldest["event"].synchronize()
                    self._poll_pending()
                    slot_idx = self._pick_free_slot()
                    if slot_idx is None:
                        continue

                with record_function(f"batch_inference_b{len(batch_frames)}"):
                    batch_size, event = self._async_inference(
                        batch_frames, ready_events, slot_idx
                    )

                self.pending_batches.append(
                    {
                        "slot_idx": slot_idx,
                        "batch_size": batch_size,
                        "cam_ids": cam_ids,
                        "event": event,
                        "timestamp": time.time(),
                    }
                )
                self._slot_idx = (slot_idx + 1) % self.num_streams

                if self._enable_profiler and self._profiler_ctx is not None:
                    self._batch_count += 1
                    if self._batch_count >= self._profiler_batches:
                        self._stop_profiler()

            except Exception as e:
                logger.error(f"Error in inference loop: {e}", exc_info=True)
                time.sleep(0.1)

        self._stop_profiler()
        logger.info("InferenceEngine stopped")

    def stop(self):
        self.running = False
        logger.info("Stopping InferenceEngine...")
