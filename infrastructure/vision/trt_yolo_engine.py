"""TensorRT YOLO detect: 1 engine, N execution context, execute_async_v3.

YOLO26 end2end engine output (B, 300, 6) = xyxy+conf+cls — không NMS CPU.
Engine hiện tại batch cố định 32: copy N frame rồi pad zero.
"""
import json
from pathlib import Path

import torch

from config.settings import settings
from utils.setup_log import setup_logger

logger = setup_logger("trt_yolo_engine", "logs/inference_engine/log")


def _engine_bytes(path: str) -> bytes:
    data = Path(path).read_bytes()
    try:
        meta_len = int.from_bytes(data[:4], "little")
        if 8 < meta_len < 2_000_000:
            json.loads(data[4 : 4 + meta_len].decode("utf-8"))
            return data[4 + meta_len :]
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        pass
    return data


class TrtExecSlot:
    """1 IExecutionContext + buffer I/O + CUDA stream. Không dùng chung với slot khác."""

    def __init__(
        self, engine, input_name, output_name, max_batch, height, width, in_dtype, out_dtype, device
    ):
        self.height = height
        self.width = width
        self.input_name = input_name
        self.output_name = output_name
        self.device = device
        self.fixed_batch = max_batch
        self.context = engine.create_execution_context()
        self.context.set_input_shape(input_name, (max_batch, 3, height, width))
        out_shape = tuple(self.context.get_tensor_shape(output_name))
        self.input = torch.zeros((max_batch, 3, height, width), dtype=in_dtype, device=device)
        self.output = torch.empty(out_shape, dtype=out_dtype, device=device)
        self.context.set_tensor_address(input_name, self.input.data_ptr())
        self.context.set_tensor_address(output_name, self.output.data_ptr())
        self.stream = torch.cuda.Stream()

    def copy_batch(self, frames_batch):
        n = min(len(frames_batch), self.fixed_batch)
        for i, frame in enumerate(frames_batch[:n]):
            if not isinstance(frame, torch.Tensor):
                frame = torch.from_numpy(frame).to(self.device)
            if frame.dtype == torch.uint8:
                src = frame.float().div_(255.0)
            elif frame.max() > 1.5:
                src = frame.div_(255.0)
            else:
                src = frame.float()
            if self.input.dtype == torch.float16:
                src = src.half()
            self.input[i].copy_(src)
        if n < self.fixed_batch:
            self.input[n:].zero_()
        return n

    def infer_async(self, batch_size):
        # Engine YOLO26 static batch=32 — luôn execute full 32, slot thừa đã zero.
        stream = self.stream
        self.context.set_input_shape(
            self.input_name, (self.fixed_batch, 3, self.height, self.width)
        )
        self.context.set_tensor_address(self.input_name, self.input.data_ptr())
        self.context.set_tensor_address(self.output_name, self.output.data_ptr())
        ok = self.context.execute_async_v3(stream_handle=stream.cuda_stream)
        if not ok:
            raise RuntimeError("execute_async_v3 failed")
        # enable_timing=True để consumer đo được elapsed_time (GPU time).
        # Event không bật timing → elapsed_time trả CUDA invalid resource handle.
        done = torch.cuda.Event(enable_timing=True)
        done.record(stream)
        return done, batch_size

    def nms_ready(self, batch_size, conf=None, max_det=15):
        """Pack output end2end (B,300,6) → list[Tensor (K,6)]. Không gọi NMS CPU."""
        if conf is None:
            conf = settings.THRESHOLD_DETECT
        preds = self.output[:batch_size].float()
        results = []
        for i in range(batch_size):
            det = preds[i]
            if det.numel() == 0:
                results.append(det.new_zeros((0, 6)))
                continue
            mask = det[:, 4] > conf
            kept = det[mask]
            if kept.shape[0] > max_det:
                _, idx = kept[:, 4].topk(max_det)
                kept = kept[idx]
            results.append(kept.contiguous())
        return results


class TrtYoloEngine:
    """1 engine deserialize; N slot (context + I/O + stream). Output list[Tensor (N,6)]."""

    def __init__(self, engine_path, max_batch, height, width, num_contexts=1, device="cuda"):
        import tensorrt as trt

        self.height = height
        self.width = width
        self.max_batch = max_batch
        self.device = device
        self.input_name = "images"
        self.output_name = None
        self.num_contexts = max(1, int(num_contexts))

        logger_trt = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(logger_trt)
        self.engine = runtime.deserialize_cuda_engine(_engine_bytes(engine_path))
        if self.engine is None:
            raise RuntimeError(f"Failed to deserialize TensorRT engine: {engine_path}")

        in_shape = tuple(self.engine.get_tensor_shape(self.input_name))
        if in_shape[0] > 0 and in_shape[0] != max_batch:
            logger.warning(
                f"Engine batch={in_shape[0]} khác max_batch={max_batch} — dùng batch engine"
            )
            max_batch = int(in_shape[0])
            self.max_batch = max_batch

        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            if self.engine.get_tensor_mode(name) == trt.TensorIOMode.OUTPUT:
                self.output_name = name
                break
        if not self.output_name:
            raise RuntimeError("Engine has no output tensor")

        in_dtype = torch.float32
        out_dtype = torch.float32
        if self.engine.get_tensor_dtype(self.input_name) == trt.DataType.HALF:
            in_dtype = torch.float16
        if self.engine.get_tensor_dtype(self.output_name) == trt.DataType.HALF:
            out_dtype = torch.float16

        self.slots = [
            TrtExecSlot(
                self.engine,
                self.input_name,
                self.output_name,
                max_batch,
                height,
                width,
                in_dtype,
                out_dtype,
                device,
            )
            for _ in range(self.num_contexts)
        ]
        out_shape = tuple(self.slots[0].output.shape)
        logger.info(
            f"TRT engine ready contexts={self.num_contexts} "
            f"input=({max_batch},3,{height},{width}) output={out_shape}"
        )

    def copy_batch(self, slot_idx, frames_batch):
        return self.slots[slot_idx].copy_batch(frames_batch)

    def infer_async(self, slot_idx, batch_size):
        return self.slots[slot_idx].infer_async(batch_size)

    def nms_ready(self, slot_idx, batch_size, conf=None, max_det=15):
        return self.slots[slot_idx].nms_ready(batch_size, conf=conf, max_det=max_det)
