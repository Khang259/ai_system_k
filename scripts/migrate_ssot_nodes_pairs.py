"""
Migrate SSOT: orphan nodes + bỏ pairs.zone_id + sync nodes.zone từ camera.

1) Node `camera_id` null / thiếu / trỏ cam không tồn tại
   → xóa pairs chứa node → xóa ROI key (mọi cam) → xóa node
2) Sync `nodes.zone_id` = `cameras.zone_id` theo camera_id
3) `$unset` field `zone_id` trên mọi document `pairs`

Chạy:
  .venv\\Scripts\\python.exe scripts/migrate_ssot_nodes_pairs.py --dry-run
  .venv\\Scripts\\python.exe scripts/migrate_ssot_nodes_pairs.py
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional, Set

from pymongo import MongoClient

MONGO_URI = "mongodb://127.0.0.1:27018"
DB_NAME = "db_kortek"


def _cam_ids(cams) -> Set[int]:
    out: Set[int] = set()
    for doc in cams.find({}, {"cameraId": 1}):
        cid = doc.get("cameraId")
        if cid is not None:
            out.add(int(cid))
    return out


def _delete_pairs_for_node(pairs, node_id: str, dry_run: bool) -> List[str]:
    deleted: List[str] = []
    for doc in pairs.find(
        {"$or": [{"start_point": node_id}, {"end_point": node_id}]},
        {"start_point": 1, "end_point": 1},
    ):
        start = doc.get("start_point") or ""
        end = doc.get("end_point")
        key = f"{start}:{end or '_'}"
        deleted.append(key)
        if not dry_run:
            pairs.delete_one(
                {"start_point": start, "end_point": end}
            )
    return deleted


def _unset_roi_keys(cams, node_id: str, dry_run: bool) -> int:
    n = 0
    for cam in cams.find({"rois." + node_id: {"$exists": True}}, {"cameraId": 1}):
        cid = cam.get("cameraId")
        n += 1
        if not dry_run:
            cams.update_one(
                {"cameraId": cid},
                {"$unset": {f"rois.{node_id}": ""}},
            )
    return n


def migrate_orphans(db, dry_run: bool) -> int:
    cams = db["cameras"]
    nodes = db["nodes"]
    pairs = db["pairs"]
    valid = _cam_ids(cams)

    orphans: List[Dict[str, Any]] = []
    for node in nodes.find({}, {"node_id": 1, "camera_id": 1, "zone_id": 1}):
        cid = node.get("camera_id")
        if cid is None:
            orphans.append(node)
            continue
        try:
            if int(cid) not in valid:
                orphans.append(node)
        except (TypeError, ValueError):
            orphans.append(node)

    print(f"Orphan / invalid-camera nodes: {len(orphans)}")
    removed = 0
    for node in orphans:
        nid = node.get("node_id") or ""
        print(f"  drop node {nid} camera_id={node.get('camera_id')!r}")
        pair_keys = _delete_pairs_for_node(pairs, nid, dry_run)
        if pair_keys:
            print(f"    pairs: {pair_keys}")
        roi_n = _unset_roi_keys(cams, nid, dry_run)
        if roi_n:
            print(f"    rois unset on {roi_n} camera(s)")
        if not dry_run and nid:
            nodes.delete_one({"node_id": nid})
            removed += 1
        elif dry_run:
            removed += 1
    return removed


def sync_node_zones(db, dry_run: bool) -> int:
    cams = db["cameras"]
    nodes = db["nodes"]
    cam_zone: Dict[int, str] = {}
    for cam in cams.find({}, {"cameraId": 1, "zone_id": 1}):
        cid = cam.get("cameraId")
        if cid is None:
            continue
        cam_zone[int(cid)] = str(cam.get("zone_id") or "").upper()

    updated = 0
    for node in nodes.find({}, {"node_id": 1, "camera_id": 1, "zone_id": 1}):
        cid = node.get("camera_id")
        if cid is None:
            continue
        try:
            key = int(cid)
        except (TypeError, ValueError):
            continue
        want = cam_zone.get(key, "")
        have = str(node.get("zone_id") or "").upper()
        if want and want != have:
            print(
                f"  sync zone {node.get('node_id')}: {have!r} -> {want!r} (cam {key})"
            )
            if not dry_run:
                nodes.update_one(
                    {"node_id": node.get("node_id")},
                    {"$set": {"zone_id": want}},
                )
            updated += 1
    print(f"Node zones synced: {updated}")
    return updated


def unset_pair_zones(db, dry_run: bool) -> int:
    pairs = db["pairs"]
    count = pairs.count_documents({"zone_id": {"$exists": True}})
    print(f"Pairs with zone_id field: {count}")
    if count and not dry_run:
        result = pairs.update_many({}, {"$unset": {"zone_id": ""}})
        print(f"  unset modified: {result.modified_count}")
        return int(result.modified_count)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate orphan nodes + pair zone_id + sync node zones"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uri", default=MONGO_URI)
    parser.add_argument("--db", default=DB_NAME)
    args = parser.parse_args()

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    db = client[args.db]

    print("=== 1) Orphan nodes ===")
    migrate_orphans(db, args.dry_run)
    print("=== 2) Sync node.zone_id from camera ===")
    sync_node_zones(db, args.dry_run)
    print("=== 3) Unset pairs.zone_id ===")
    unset_pair_zones(db, args.dry_run)

    if args.dry_run:
        print("\n[dry-run] No DB write.")
    else:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
