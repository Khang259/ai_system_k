"""
Xóa rois trên mọi camera trừ cameraId 1 và 2.

Giữ nguyên rois của cam 1 (starts) và cam 2 (ends).
Cam khác → rois = {} để tránh nhiều cam ghi đè cùng node_id.

Chạy:
  .venv\\Scripts\\python.exe scripts/cleanup_orphan_rois.py
  # hoặc dry-run:
  .venv\\Scripts\\python.exe scripts/cleanup_orphan_rois.py --dry-run
"""
from __future__ import annotations

import argparse
import sys

from pymongo import MongoClient

MONGO_URI = "mongodb://127.0.0.1:27018"
DB_NAME = "db_kortek"
KEEP_CAMERA_IDS = {1, 2}


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear rois on cameras except 1 and 2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ in, không ghi DB",
    )
    parser.add_argument("--uri", default=MONGO_URI)
    parser.add_argument("--db", default=DB_NAME)
    args = parser.parse_args()

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    col = client[args.db]["cameras"]

    to_clear = list(
        col.find(
            {"cameraId": {"$nin": sorted(KEEP_CAMERA_IDS)}},
            {"cameraId": 1, "rois": 1, "name": 1},
        ).sort("cameraId", 1)
    )

    print(f"Keep rois: cameraId in {sorted(KEEP_CAMERA_IDS)}")
    for cam in col.find(
        {"cameraId": {"$in": sorted(KEEP_CAMERA_IDS)}},
        {"cameraId": 1, "rois": 1},
    ).sort("cameraId", 1):
        keys = list((cam.get("rois") or {}).keys())
        print(f"  cam {cam.get('cameraId')}: {keys}")

    print(f"\nWill clear rois: {len(to_clear)} cameras")
    cleared = 0
    for cam in to_clear:
        cid = cam.get("cameraId")
        keys = list((cam.get("rois") or {}).keys())
        if not keys:
            print(f"  cam {cid}: already empty")
            continue
        print(f"  cam {cid}: {keys} -> {{}}")
        if not args.dry_run:
            col.update_one({"cameraId": cid}, {"$set": {"rois": {}}})
            cleared += 1

    if args.dry_run:
        print("\n[dry-run] No DB write.")
    else:
        print(f"\nDone. Cleared rois on {cleared} cameras.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
