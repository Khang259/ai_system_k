"""
Scale ROI trong Mongo theo resolution mới (MODEL_WIDTH × MODEL_HEIGHT).

ROI cũ vẽ trên khung 1280×736; engine/infer giờ dùng settings.MODEL_*.
Script nhân [x, y, w, h] theo sx/sy và ghi lại ref_width / ref_height.

Công thức:
  sx = new_w / old_w
  sy = new_h / old_h
  [x', y', w', h'] = [x*sx, y*sy, w*sx, h*sy]  (clamp trong khung mới)

Chạy:
  .venv\\Scripts\\python.exe scripts/scale_rois_resolution.py --dry-run
  .venv\\Scripts\\python.exe scripts/scale_rois_resolution.py
  .venv\\Scripts\\python.exe scripts/scale_rois_resolution.py --from-w 1280 --from-h 736
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings

# Khung ROI cũ trước khi đổi MODEL_* (W×H).
DEFAULT_FROM_W = 1280
DEFAULT_FROM_H = 736


def _as_box(entry: Any) -> Optional[List[float]]:
    if isinstance(entry, dict):
        box = entry.get("roi")
    elif isinstance(entry, (list, tuple)):
        box = entry
    else:
        return None
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        return [float(v) for v in box]
    except (TypeError, ValueError):
        return None


def _entry_ref(entry: Any) -> Tuple[Optional[int], Optional[int]]:
    if not isinstance(entry, dict):
        return None, None
    rw = entry.get("ref_width", entry.get("refWidth"))
    rh = entry.get("ref_height", entry.get("refHeight"))
    try:
        rw_i = int(rw) if rw is not None else None
    except (TypeError, ValueError):
        rw_i = None
    try:
        rh_i = int(rh) if rh is not None else None
    except (TypeError, ValueError):
        rh_i = None
    return rw_i, rh_i


def _scale_box(
    box: List[float],
    sx: float,
    sy: float,
    new_w: int,
    new_h: int,
) -> List[float]:
    x, y, w, h = box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy
    # Clamp trong khung mới; giữ w,h > 0 nếu còn chỗ.
    x = min(max(0.0, x), float(new_w - 1))
    y = min(max(0.0, y), float(new_h - 1))
    w = max(1.0, min(w, float(new_w) - x))
    h = max(1.0, min(h, float(new_h) - y))
    return [
        round(x, 3),
        round(y, 3),
        round(w, 3),
        round(h, 3),
    ]


def _build_entry(
    old: Any,
    new_box: List[float],
    new_w: int,
    new_h: int,
    node_id: str,
) -> Dict[str, Any]:
    if isinstance(old, dict):
        is_start = bool(old.get("start"))
        is_end = bool(old.get("end"))
        if not is_start and not is_end:
            is_start = str(node_id).startswith("start_")
            is_end = not is_start
        out = dict(old)
        out["roi"] = new_box
        out["start"] = is_start
        out["end"] = is_end
        out["ref_width"] = new_w
        out["ref_height"] = new_h
        out.pop("refWidth", None)
        out.pop("refHeight", None)
        return out
    is_start = str(node_id).startswith("start_")
    return {
        "roi": new_box,
        "start": is_start,
        "end": not is_start,
        "ref_width": new_w,
        "ref_height": new_h,
    }


def scale_rois(
    col,
    *,
    from_w: int,
    from_h: int,
    to_w: int,
    to_h: int,
    dry_run: bool,
    force: bool,
) -> int:
    if from_w <= 0 or from_h <= 0 or to_w <= 0 or to_h <= 0:
        raise ValueError("resolution phải > 0")

    sx = to_w / float(from_w)
    sy = to_h / float(from_h)
    print(f"Scale {from_w}x{from_h} -> {to_w}x{to_h}  (sx={sx:.6f}, sy={sy:.6f})")
    if math.isclose(sx, 1.0) and math.isclose(sy, 1.0):
        print("from == to - khong can scale.")
        return 0

    updated_cams = 0
    updated_rois = 0
    skipped = 0

    for cam in col.find({}, {"cameraId": 1, "name": 1, "rois": 1}).sort("cameraId", 1):
        cid = cam.get("cameraId")
        rois = cam.get("rois") or {}
        if not isinstance(rois, dict) or not rois:
            continue

        new_rois: Dict[str, Any] = {}
        cam_changed = False
        print(f"\ncam {cid} ({cam.get('name') or ''}): {len(rois)} ROI")

        for node_id, entry in rois.items():
            box = _as_box(entry)
            if box is None:
                print(f"  SKIP {node_id}: box khong hop le - giu nguyen")
                new_rois[node_id] = entry
                skipped += 1
                continue

            ref_w, ref_h = _entry_ref(entry)
            # Đã đúng target → bỏ qua (trừ --force).
            if (
                not force
                and ref_w == to_w
                and ref_h == to_h
            ):
                print(f"  skip {node_id}: da {to_w}x{to_h} {box}")
                new_rois[node_id] = entry
                skipped += 1
                continue

            # Scale từ ref lưu trên ROI nếu có; không thì dùng --from-*.
            src_w = ref_w if ref_w and ref_w > 0 else from_w
            src_h = ref_h if ref_h and ref_h > 0 else from_h
            local_sx = to_w / float(src_w)
            local_sy = to_h / float(src_h)
            new_box = _scale_box(box, local_sx, local_sy, to_w, to_h)
            new_entry = _build_entry(entry, new_box, to_w, to_h, str(node_id))
            new_rois[node_id] = new_entry
            cam_changed = True
            updated_rois += 1
            print(
                f"  {node_id}: {box} @{src_w}x{src_h} -> {new_box} @{to_w}x{to_h}"
            )

        if cam_changed:
            updated_cams += 1
            if not dry_run:
                col.update_one({"cameraId": cid}, {"$set": {"rois": new_rois}})

    print(
        f"\nSummary: cams_updated={updated_cams}, rois_scaled={updated_rois}, "
        f"skipped={skipped}"
    )
    return updated_rois


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scale ROI boxes từ resolution cũ sang MODEL_WIDTH×MODEL_HEIGHT"
    )
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in, không ghi DB")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Scale lại cả ROI đã có ref = target",
    )
    parser.add_argument("--uri", default=settings.MONGODB_URL)
    parser.add_argument("--db", default=settings.MONGODB_DB)
    parser.add_argument("--from-w", type=int, default=DEFAULT_FROM_W)
    parser.add_argument("--from-h", type=int, default=DEFAULT_FROM_H)
    parser.add_argument(
        "--to-w",
        type=int,
        default=settings.MODEL_WIDTH,
        help=f"mặc định settings.MODEL_WIDTH={settings.MODEL_WIDTH}",
    )
    parser.add_argument(
        "--to-h",
        type=int,
        default=settings.MODEL_HEIGHT,
        help=f"mặc định settings.MODEL_HEIGHT={settings.MODEL_HEIGHT}",
    )
    args = parser.parse_args()

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    col = client[args.db]["cameras"]

    print(f"Mongo: {args.uri} / {args.db}")
    n = scale_rois(
        col,
        from_w=args.from_w,
        from_h=args.from_h,
        to_w=args.to_w,
        to_h=args.to_h,
        dry_run=args.dry_run,
        force=args.force,
    )
    if args.dry_run:
        print("\n[dry-run] No DB write.")
    else:
        print(f"\nDone. Scaled {n} ROI(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
