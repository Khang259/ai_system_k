"""
Export YOLO → ONNX → TensorRT engine.

Batch cố định 32 (khớp ONNX dynamic=False). H×W = MODEL_HEIGHT×MODEL_WIDTH.
"""
import pathlib
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if platform.system() == "Windows":
    pathlib.PosixPath = pathlib.WindowsPath

from ultralytics import YOLO

from config.settings import settings

PT_PATH = Path("models/model_test.pt")
ONNX_PATH = Path("models/model_test.onnx")
ENGINE_PATH = Path(settings.MODEL_PATH)
INPUT_NAME = "images"
FIXED_BATCH = 32


def export_onnx():
    h, w = settings.MODEL_HEIGHT, settings.MODEL_WIDTH
    print(f"Export ONNX fixed batch={FIXED_BATCH}, imgsz=[{h}, {w}]")
    model = YOLO(str(PT_PATH))
    model.export(
        format="onnx",
        dynamic=False,
        batch=FIXED_BATCH,
        imgsz=[h, w],
        simplify=True,
    )
    if not ONNX_PATH.exists():
        raise FileNotFoundError(f"ONNX not found: {ONNX_PATH}")
    print(f"ONNX: {ONNX_PATH}")


def build_engine():
    import torch
    import tensorrt as trt

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA không available — TensorRT cần GPU để build engine")
    torch.cuda.init()
    print(f"Build TRT on {torch.cuda.get_device_name(0)}")
    h, w = settings.MODEL_HEIGHT, settings.MODEL_WIDTH
    b = FIXED_BATCH

    logger = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(logger)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, logger)

    onnx_bytes = ONNX_PATH.read_bytes()
    if not parser.parse(onnx_bytes):
        for i in range(parser.num_errors):
            print(parser.get_error(i))
        raise RuntimeError("ONNX parse failed")

    config = builder.create_builder_config()
    config.set_flag(trt.BuilderFlag.FP16)
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 2 * 1024 * 1024 * 1024)

    # ONNX static batch=32 → profile min=opt=max phải = 32
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
    import tensorrt as trt
    logger = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(ENGINE_PATH.read_bytes())
    name = engine.get_tensor_name(0)
    shape = tuple(engine.get_tensor_shape(name))
    prof = engine.get_tensor_profile_shape(name, 0)
    print(f"Inspect {name}: shape={shape}")
    print(f"  min={tuple(prof[0])} opt={tuple(prof[1])} max={tuple(prof[2])}")
    assert tuple(prof[0]) == (FIXED_BATCH, 3, settings.MODEL_HEIGHT, settings.MODEL_WIDTH)
    assert tuple(prof[1]) == (FIXED_BATCH, 3, settings.MODEL_HEIGHT, settings.MODEL_WIDTH)
    assert tuple(prof[2]) == (FIXED_BATCH, 3, settings.MODEL_HEIGHT, settings.MODEL_WIDTH)


if __name__ == "__main__":
    if not ONNX_PATH.exists():
        export_onnx()
    else:
        print(f"Reuse ONNX: {ONNX_PATH}")
    build_engine()
    inspect_engine()
    print(f"Done. Engine fixed batch={FIXED_BATCH}.")
