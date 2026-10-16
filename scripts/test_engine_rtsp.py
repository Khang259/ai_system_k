"""
Smoke-test TensorRT engine với 1 RTSP stream.

Chạy:
  uv run python scripts/test_engine_rtsp.py
  uv run python scripts/test_engine_rtsp.py --seconds 30 --save-dir tmp/engine_test
  uv run python scripts/test_engine_rtsp.py --show
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import torch

from config.settings import settings
from infrastructure.vision.gpu_video_decoder import GPUVideoDecoder
from infrastructure.vision.preview_draw import draw_overlay, frame_to_bgr
from infrastructure.vision.trt_yolo_engine import TrtYoloEngine
from utils.rtsp_url import encode_rtsp_userinfo

DEFAULT_ENGINE = "models/KortekFL01102601.engine"
DEFAULT_RTSP = "rtsp://admin:Kortek2026#@192.168.50.113:554/Streaming/Channels/102"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test TRT engine trên RTSP")
    p.add_argument("--engine", default=DEFAULT_ENGINE, help="Đường dẫn file .engine")
    p.add_argument("--rtsp", default=DEFAULT_RTSP, help="URL RTSP (password có # cũng OK)")
    p.add_argument("--seconds", type=float, default=20.0, help="Thời gian chạy (0 = vô hạn)")
    p.add_argument("--conf", type=float, default=None, help="Ngưỡng conf (mặc định settings)")
    p.add_argument("--save-dir", default="", help="Thư mục ghi JPEG mỗi N frame")
    p.add_argument("--save-every", type=int, default=30, help="Ghi 1 ảnh mỗi N frame inference")
    p.add_argument("--show", action="store_true", help="Mở cửa sổ OpenCV xem live")
    p.add_argument(
        "--wait-first",
        type=float,
        default=settings.DECODE_WAIT_FIRST_FRAME_SEC,
        help="Timeout chờ frame đầu (giây)",
    )
    return p.parse_args()


def _fmt_det(row) -> str:
    x1, y1, x2, y2, conf, cls_id = [float(v) for v in row[:6]]
    return (
        f"cls={int(cls_id)} conf={conf:.3f} "
        f"xyxy=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f})"
    )


def main() -> int:
    args = _parse_args()
    engine_path = Path(args.engine)
    if not engine_path.is_file():
        print(f"[ERR] Không thấy engine: {engine_path}")
        return 1
    if not torch.cuda.is_available():
        print("[ERR] CUDA không available — script cần GPU")
        return 1

    rtsp = encode_rtsp_userinfo(args.rtsp)
    h, w = settings.MODEL_HEIGHT, settings.MODEL_WIDTH
    conf = args.conf if args.conf is not None else settings.THRESHOLD_DETECT
    save_dir = Path(args.save_dir) if args.save_dir else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)

    print(f"GPU     : {torch.cuda.get_device_name(0)}")
    print(f"Engine  : {engine_path}")
    print(f"RTSP    : {rtsp}")
    print(f"Imgsz   : {h}x{w}  conf>={conf}")
    print(f"Duration: {'infinite' if args.seconds <= 0 else f'{args.seconds}s'}")

    print("Loading TRT engine...")
    engine = TrtYoloEngine(
        engine_path=str(engine_path),
        max_batch=settings.INFERENCE_MAX_BATCH_SIZE,
        height=h,
        width=w,
        num_contexts=1,
        device="cuda",
    )
    print(f"Engine batch fixed={engine.max_batch}")

    print("Opening RTSP (NVDEC)...")
    cap = GPUVideoDecoder(rtsp, width=w, height=h, camera_index=0)
    if not cap.isOpened():
        print("[ERR] Không mở được RTSP / ffmpeg")
        return 1
    if not cap.wait_ready(timeout=args.wait_first):
        print(f"[ERR] Timeout {args.wait_first}s chờ frame đầu")
        cap.release()
        return 1
    print("First frame OK — bắt đầu infer")

    n_read = 0
    n_infer = 0
    n_det = 0
    t0 = time.perf_counter()
    t_infer_sum = 0.0
    deadline = None if args.seconds <= 0 else (t0 + args.seconds)

    try:
        while True:
            if deadline is not None and time.perf_counter() >= deadline:
                break

            ret, frame, decode_event = cap.read()
            if not ret or frame is None:
                if not cap.isOpened():
                    print("[ERR] Mất stream")
                    break
                time.sleep(0.005)
                continue

            n_read += 1
            if decode_event is not None:
                decode_event.synchronize()

            t_inf0 = time.perf_counter()
            batch_n = engine.copy_batch(0, [frame])
            done_event, _ = engine.infer_async(0, batch_n)
            done_event.synchronize()
            results = engine.nms_ready(0, batch_n, conf=conf, max_det=15)
            t_infer_sum += time.perf_counter() - t_inf0
            n_infer += 1

            dets = results[0] if results else None
            det_n = int(dets.shape[0]) if dets is not None else 0
            n_det += det_n

            if n_infer == 1 or n_infer % 30 == 0:
                elapsed = time.perf_counter() - t0
                fps = n_infer / elapsed if elapsed > 0 else 0.0
                ms = (t_infer_sum / n_infer) * 1000.0
                print(
                    f"[{n_infer:5d}] fps={fps:5.1f}  infer={ms:5.1f}ms  "
                    f"dets={det_n}  read={n_read}"
                )
                if det_n > 0:
                    for row in dets[:5]:
                        print(f"         {_fmt_det(row)}")

            need_bgr = args.show or (
                save_dir is not None and n_infer % max(1, args.save_every) == 0
            )
            if need_bgr:
                bgr = frame_to_bgr(frame)
                overlay = draw_overlay(bgr, dets, rois=None)
                if save_dir is not None and n_infer % max(1, args.save_every) == 0:
                    out = save_dir / f"frame_{n_infer:06d}.jpg"
                    cv2.imwrite(str(out), overlay)
                    print(f"         saved {out}")
                if args.show:
                    cv2.imshow("engine_rtsp_test", overlay)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        print("Quit (q)")
                        break
    except KeyboardInterrupt:
        print("\nStopped by Ctrl+C")
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - t0
    avg_ms = (t_infer_sum / n_infer * 1000.0) if n_infer else 0.0
    fps = n_infer / elapsed if elapsed > 0 else 0.0
    print("---")
    print(
        f"Done: read={n_read} infer={n_infer} total_dets={n_det} "
        f"elapsed={elapsed:.1f}s fps={fps:.1f} avg_infer={avg_ms:.1f}ms"
    )
    return 0 if n_infer > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
