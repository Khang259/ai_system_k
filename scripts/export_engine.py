"""
Export YOLO → ONNX (end2end + NMS) → TensorRT engine.

Khớp TrtYoloEngine: output (B, max_det, 6) = xyxy+conf+cls.
Batch cố định = FIXED_BATCH. H×W = MODEL_HEIGHT×MODEL_WIDTH.

Lưu ý: Ultralytics export ONNX làm torch.cuda.device_count()=0 trong
cùng process → build TRT phải chạy ở subprocess mới (--build-only).
"""
import argparse
import pathlib
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if platform.system() == "Windows":
    pathlib.PosixPath = pathlib.WindowsPath

from config.settings import settings

PT_PATH = Path("models/KortekFL01102601.pt")
ONNX_PATH = Path("models/KortekFL01102601.onnx")
ENGINE_PATH = Path("models/KortekFL01102601.engine")
INPUT_NAME = "images"
FIXED_BATCH = 16
# Khớp Ultralytics default / TrtYoloEngine comment (B, 300, 6)
MAX_DET = 300


def export_onnx():
    """Export ONNX có NMS nhúng → output end2end (B, max_det, 6)."""
    from ultralytics import YOLO

    h, w = settings.MODEL_HEIGHT, settings.MODEL_WIDTH
    conf = settings.THRESHOLD_DETECT
    print(
        f"Export ONNX end2end nms=True batch={FIXED_BATCH} "
        f"imgsz=[{h}, {w}] max_det={MAX_DET} conf={conf}"
    )
    model = YOLO(str(PT_PATH))
    model.export(
        format="onnx",
        dynamic=False,
        batch=FIXED_BATCH,
        imgsz=[h, w],
        simplify=True,
        nms=True,           # nhúng NMS → end2end, khớp TrtYoloEngine
        conf=conf,
        iou=0.45,
        max_det=MAX_DET,
        agnostic_nms=False,
    )
    if not ONNX_PATH.exists():
        raise FileNotFoundError(f"ONNX not found: {ONNX_PATH}")
    print(f"ONNX: {ONNX_PATH}")


def build_engine():
    import torch
    import tensorrt as trt

    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        raise RuntimeError(
            "CUDA không available / device_count=0. "
            "Nếu vừa export ONNX trong cùng process: dùng --build-only "
            "(subprocess). nvidia-smi để xem process compute đang giữ GPU."
        )
    torch.cuda.init()
    print(f"Build TRT on {torch.cuda.get_device_name(0)}")
    h, w = settings.MODEL_HEIGHT, settings.MODEL_WIDTH
    b = FIXED_BATCH

    logger = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(logger)
    network = builder.create_network(
        1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    )
    parser = trt.OnnxParser(network, logger)

    onnx_bytes = ONNX_PATH.read_bytes()
    if not parser.parse(onnx_bytes):
        for i in range(parser.num_errors):
            print(parser.get_error(i))
        raise RuntimeError("ONNX parse failed")

    config = builder.create_builder_config()
    config.set_flag(trt.BuilderFlag.FP16)
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 2 * 1024 * 1024 * 1024)

    # ONNX static batch → profile min=opt=max phải = FIXED_BATCH
    profile = builder.create_optimization_profile()
    profile.set_shape(
        INPUT_NAME,
        min=(b, 3, h, w),
        opt=(b, 3, h, w),
        max=(b, 3, h, w),
    )
    config.add_optimization_profile(profile)

    print(f"TRT profile {INPUT_NAME}: min=opt=max=({b},3,{h},{w})")
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError("TensorRT build failed")

    ENGINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENGINE_PATH.write_bytes(bytes(serialized))
    print(f"Engine: {ENGINE_PATH} ({ENGINE_PATH.stat().st_size / 1e6:.1f} MB)")


def inspect_engine():
    """Verify input + output khớp TrtYoloEngine (end2end)."""
    import tensorrt as trt

    logger = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(ENGINE_PATH.read_bytes())

    in_name = None
    out_name = None
    for i in range(engine.num_io_tensors):
        name = engine.get_tensor_name(i)
        mode = engine.get_tensor_mode(name)
        shape = tuple(engine.get_tensor_shape(name))
        print(f"  tensor {name}: mode={mode} shape={shape}")
        if mode == trt.TensorIOMode.INPUT and in_name is None:
            in_name = name
        if mode == trt.TensorIOMode.OUTPUT and out_name is None:
            out_name = name

    assert in_name is not None, "Engine missing input"
    assert out_name is not None, "Engine missing output"

    in_shape = tuple(engine.get_tensor_shape(in_name))
    out_shape = tuple(engine.get_tensor_shape(out_name))
    expected_in = (FIXED_BATCH, 3, settings.MODEL_HEIGHT, settings.MODEL_WIDTH)
    assert in_shape == expected_in, f"Input {in_shape} != {expected_in}"

    # End2end: (B, max_det, 6) — KHÔNG phải raw (B, 4+nc, N)
    assert len(out_shape) == 3, f"Output rank phải 3 (B,max_det,6), nhận {out_shape}"
    assert out_shape[0] == FIXED_BATCH, f"Output batch {out_shape[0]} != {FIXED_BATCH}"
    assert out_shape[2] == 6, (
        f"Output last dim phải = 6 (xyxy+conf+cls), nhận {out_shape} — "
        "ONNX có thể vẫn raw (thiếu nms=True)"
    )
    print(f"Inspect OK input={in_shape} output={out_shape} (end2end)")


def _run_build_in_fresh_process() -> None:
    """Build TRT trong process mới — tránh device_count=0 sau Ultralytics export."""
    script = Path(__file__).resolve()
    print("Spawn subprocess --build-only (CUDA fresh)...")
    proc = subprocess.run(
        [sys.executable, str(script), "--build-only"],
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export end2end ONNX → TensorRT")
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Chỉ build+inspect từ ONNX có sẵn (process mới, CUDA sạch)",
    )
    args = parser.parse_args()

    if args.build_only:
        if not ONNX_PATH.is_file():
            raise FileNotFoundError(f"Thiếu ONNX: {ONNX_PATH} — chạy export trước")
        build_engine()
        inspect_engine()
        print(f"Done. Engine end2end batch={FIXED_BATCH} max_det={MAX_DET}.")
    else:
        # Luôn export lại ONNX: file cũ có thể là raw (B,5,N)
        if ONNX_PATH.exists():
            print(f"Remove old ONNX (có thể raw): {ONNX_PATH}")
            ONNX_PATH.unlink()
        export_onnx()
        # Không gọi build_engine() cùng process — Ultralytics làm device_count=0
        _run_build_in_fresh_process()
