import threading
import queue
import time
from collections import deque
import torch
from ultralytics import YOLO
from utils.setup_log import setup_logger
import pathlib
import platform

if platform.system() == "Windows":
    pathlib.PosixPath = pathlib.WindowsPath


logger = setup_logger("inference_engine", "logs/inference_engine/log")


class InferenceEngine(threading.Thread):
    """Central inference engine với single model instance, batch processing và CUDA stream async."""

    def __init__(
        self,
        model_path,
        max_queue_size,
        max_batch_size,
        batch_timeout,
        num_streams,
        initial_paused: bool = False,
    ):
        super().__init__(daemon=True, name="InferenceEngine")

        self.model_path = model_path
        self.max_queue_size = max_queue_size
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self.num_streams = num_streams
        self.shared_queue = queue.Queue(maxsize=max_queue_size)
        self.result_queues = {}
        self.streams = []
        self.pending_batches = deque(maxlen=num_streams * 2)
        self.running = False
        self.model = None
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

    def put_frame_with_drop(self, frame, cam_id):
        try:
            self.shared_queue.put_nowait((frame, cam_id))
        except queue.Full:
            try:
                self.shared_queue.get_nowait()
            except queue.Empty:
                pass

    def _collect_batch(self):
        batch = []
        cam_ids = []
        start_time = time.time()

        while len(batch) < self.max_batch_size:
            timeout = self.batch_timeout - (time.time() - start_time)
            if timeout <= 0:
                break

            try:
                frame, cam_id = self.shared_queue.get(timeout=timeout)
                batch.append(frame)
                cam_ids.append(cam_id)
            except queue.Empty:
                break

        return batch, cam_ids

    def _load_model(self):
        try:
            self.model = YOLO(self.model_path, verbose=False)
            self.streams = [torch.cuda.Stream() for _ in range(self.num_streams)]
            self._model_ready.set()
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"Failed to load model: {e}")
            raise
        finally:
            self._load_done.set()

    def _to_model_batch(self, frames_batch):
        """CUDA uint8 CHW → BCHW float 0-1. Numpy list giữ nguyên cho YOLO."""
        first = frames_batch[0]
        if not isinstance(first, torch.Tensor):
            return frames_batch

        batch = torch.stack(frames_batch, dim=0)
        if batch.dtype == torch.uint8:
            batch = batch.float().div_(255.0)
        else:
            batch = batch.float()
            if batch.max() > 1.5:
                batch = batch.div_(255.0)
        return batch.contiguous()

    def _async_inference(self, frames_batch, stream):
        with torch.cuda.stream(stream):
            model_input = self._to_model_batch(frames_batch)
            results = self.model(
                model_input,
                conf=0.3,
                max_det=15,
                device="cuda",
                verbose=False,
                stream=True,
            )

            output = []
            for result in results:
                detections = result.boxes.data
                output.append(detections)

            event = stream.record_event()

        return output, event

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

    def run(self):
        self.running = True
        try:
            self._load_model()
        except Exception:
            return

        stream_idx = 0

        while self.running:
            try:
                if self._paused.is_set():
                    time.sleep(0.05)
                    continue

                batch_frames, cam_ids = self._collect_batch()

                if len(batch_frames) > 0:
                    stream = self.streams[stream_idx]

                    results, event = self._async_inference(batch_frames, stream)
                    self.pending_batches.append(
                        {
                            "results": results,
                            "cam_ids": cam_ids,
                            "event": event,
                            "timestamp": time.time(),
                        }
                    )

                    stream_idx = (stream_idx + 1) % self.num_streams

                completed_indices = []
                for i, batch_info in enumerate(self.pending_batches):
                    if batch_info["event"].query():
                        self._distribute_results(batch_info["results"], batch_info["cam_ids"])
                        completed_indices.append(i)

                for i in reversed(completed_indices):
                    del self.pending_batches[i]

                if len(batch_frames) == 0 and len(self.pending_batches) == 0:
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in inference loop: {e}", exc_info=True)
                time.sleep(0.1)

        logger.info("InferenceEngine stopped")

    def stop(self):
        self.running = False
        logger.info("Stopping InferenceEngine...")
