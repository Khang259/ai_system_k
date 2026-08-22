"""CPU overlay: frame CUDA/numpy → JPEG. ROI + bbox + cls/conf."""
import cv2
import numpy as np


def frame_to_bgr(frame) -> np.ndarray:
    """CHW RGB uint8 (GPU/CPU) hoặc HWC → BGR cho cv2."""
    if hasattr(frame, "detach"):
        tensor = frame.detach()
        if getattr(tensor, "is_cuda", False):
            tensor = tensor.cpu()
        arr = tensor.numpy()
    else:
        arr = np.asarray(frame)

    if arr.ndim == 3 and arr.shape[0] == 3:
        arr = np.transpose(arr, (1, 2, 0))
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.shape[-1] == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return arr


def encode_jpeg(bgr: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("cv2.imencode jpeg failed")
    return buf.tobytes()


def _as_numpy_dets(detections) -> np.ndarray:
    if detections is None:
        return np.zeros((0, 6), dtype=np.float32)
    if hasattr(detections, "detach"):
        tensor = detections.detach()
        if getattr(tensor, "is_cuda", False):
            tensor = tensor.cpu()
        return tensor.numpy()
    return np.asarray(detections, dtype=np.float32)


def overlay_meta(detections, rois, ts: float, width: int, height: int) -> dict:
    """JSON F5: rois + dets[{cls,conf,xyxy}] + ts. Toạ độ không gian infer W×H."""
    roi_out = []
    for item in rois or []:
        if isinstance(item, dict):
            box = item.get("roi")
            node_id = str(item.get("node_id") or "")
        else:
            box = item
            node_id = ""
        if not box or len(box) < 4:
            continue
        roi_out.append({
            "roi": [int(v) for v in box[:4]],
            "node_id": node_id,
        })
    dets_out = []
    arr = _as_numpy_dets(detections)
    if arr.ndim == 2 and arr.shape[1] >= 6:
        for row in arr:
            x1, y1, x2, y2, conf, cls_id = [float(v) for v in row[:6]]
            dets_out.append({
                "cls": int(cls_id),
                "conf": round(conf, 4),
                "xyxy": [x1, y1, x2, y2],
            })
    return {
        "ts": ts,
        "w": int(width),
        "h": int(height),
        "rois": roi_out,
        "dets": dets_out,
    }


def draw_overlay(bgr: np.ndarray, detections, rois) -> np.ndarray:
    """ROI [x,y,w,h] màu riêng; bbox xyxy + nhãn '{cls} {conf:.2f}'."""
    out = bgr.copy()
    for roi_dict in rois or []:
        box = roi_dict.get("roi") if isinstance(roi_dict, dict) else roi_dict
        if not box or len(box) < 4:
            continue
        x, y, w, h = [int(v) for v in box[:4]]
        node_id = ""
        if isinstance(roi_dict, dict):
            node_id = str(roi_dict.get("node_id") or "")
        color = (0, 165, 255) if node_id.startswith("end_") else (0, 220, 0)
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        if node_id:
            cv2.putText(
                out, node_id, (x, max(16, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA,
            )

    dets = _as_numpy_dets(detections)
    if dets.ndim != 2 or dets.shape[1] < 6:
        return out
    for row in dets:
        x1, y1, x2, y2, conf, cls_id = [float(v) for v in row[:6]]
        p1 = (int(x1), int(y1))
        p2 = (int(x2), int(y2))
        cv2.rectangle(out, p1, p2, (0, 255, 255), 2)
        label = f"{int(cls_id)} {conf:.2f}"
        cv2.putText(
            out, label, (p1[0], max(16, p1[1] - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA,
        )
    return out
