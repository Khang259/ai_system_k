"""
Seed topo product (zone X) từ mapping topo.xlsx — không ghi pairs.

Zones: X (có node/cam) + Y (chỉ document, chưa có node).
Cameras / nodes: thay thế theo cameraId / node_id của topo; không xoá doc khác.

    uv run python scripts/seed_topo.py
    uv run python scripts/seed_topo.py --dry-run

Không chạy khi MONGODB_DB kết thúc `_sandbox` (dùng seed_sandbox.py).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings

# (priority, code, label, camera_id) — A1 → D9
STARTS: list[tuple[int, str, str, int]] = [
    (1, "10000004", "A1", 9),
    (2, "10000066", "A2", 9),
    (3, "10000007", "A3", 9),
    (4, "10000077", "A4", 9),
    (5, "10000081", "A5", 9),
    (6, "10000085", "A6", 14),
    (7, "10000089", "A7", 14),
    (8, "10000093", "A8", 14),
    (9, "10000097", "A9", 14),
    (10, "10000010", "B1", 9),
    (11, "10000067", "B2", 9),
    (12, "10000013", "B3", 9),
    (13, "10000078", "B4", 9),
    (14, "10000082", "B5", 9),
    (15, "10000086", "B6", 14),
    (16, "10000090", "B7", 14),
    (17, "10000094", "B8", 14),
    (18, "10000098", "B9", 14),
    (19, "10000068", "C1", 8),
    (20, "10000070", "C2", 8),
    (21, "10000072", "C3", 8),
    (22, "10000079", "C4", 10),
    (23, "10000083", "C5", 10),
    (24, "10000087", "C6", 10),
    (25, "10000091", "C7", 13),
    (26, "10000095", "C8", 13),
    (27, "10000099", "C9", 13),
    (28, "10000069", "D1", 8),
    (29, "10000071", "D2", 8),
    (30, "10000073", "D3", 8),
    (31, "10000080", "D4", 10),
    (32, "10000084", "D5", 10),
    (33, "10000088", "D6", 10),
    (34, "10000092", "D7", 13),
    (35, "10000096", "D8", 13),
    (36, "10000100", "D9", 13),
]

ENDS: list[tuple[str, str, int]] = [
    ("10000105", "Line1", 15),
    ("10000106", "Line2", 16),
]

# CamN → 192.168.50.(110 + N)
CAMERA_IDS = (8, 9, 10, 13, 14, 15, 16)
RTSP_USER = "admin"
RTSP_PASS = "Kortek2026#"
RTSP_PORT = 554
RTSP_PATH = "/Streaming/Channels/102"
ZONE_X = "X"
ZONE_Y = "Y"
ROI = [0.0, 0.0, 100.0, 100.0]


def _rtsp(camera_id: int) -> str:
    ip = f"192.168.50.{110 + camera_id}"
    return f"rtsp://{RTSP_USER}:{RTSP_PASS}@{ip}:{RTSP_PORT}{RTSP_PATH}"


def _roi_doc(is_start: bool) -> dict:
    return {
        "roi": list(ROI),
        "start": is_start,
        "end": not is_start,
        "ref_width": settings.MODEL_WIDTH,
        "ref_height": settings.MODEL_HEIGHT,
    }


def _node_doc(
    node_id: str, node_type: str, camera_id: int, priority: int
) -> dict:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "zone_id": ZONE_X,
        "camera_id": camera_id,
        "priority": priority,
        "enabled": True,
        "is_under_maintenance": False,
        "maintenance_reason": "",
        "lock": {"user": False, "system": False, "orderId": None},
    }


def build_docs() -> dict:
    rois_by_cam: dict[int, dict] = {cid: {} for cid in CAMERA_IDS}
    nodes: list[dict] = []

    for priority, code, _label, camera_id in STARTS:
        node_id = f"start_{code}"
        nodes.append(_node_doc(node_id, "start", camera_id, priority))
        rois_by_cam[camera_id][node_id] = _roi_doc(is_start=True)

    for i, (code, _label, camera_id) in enumerate(ENDS, start=1):
        node_id = f"end_{code}"
        nodes.append(_node_doc(node_id, "end", camera_id, i))
        rois_by_cam[camera_id][node_id] = _roi_doc(is_start=False)

    cameras = [
        {
            "cameraId": cid,
            "name": f"Cam{cid}",
            "url": _rtsp(cid),
            "zone_id": ZONE_X,
            "enabled": True,
            "rois": rois_by_cam[cid],
        }
        for cid in CAMERA_IDS
    ]

    zones = [
        {"zone_id": ZONE_X, "name": "Zone X", "enabled": True},
        {"zone_id": ZONE_Y, "name": "Zone Y", "enabled": True},
    ]
    return {"cameras": cameras, "nodes": nodes, "zones": zones}


def _apply(db, docs: dict, dry_run: bool) -> None:
    cam_ids = [c["cameraId"] for c in docs["cameras"]]
    node_ids = [n["node_id"] for n in docs["nodes"]]
    zone_ids = [z["zone_id"] for z in docs["zones"]]

    if dry_run:
        print(f"[dry-run] zones upsert: {zone_ids}")
        print(f"[dry-run] cameras replace cameraId in {cam_ids}")
        print(f"[dry-run] nodes replace node_id ({len(node_ids)} docs)")
        return

    for z in docs["zones"]:
        db["zones"].update_one(
            {"zone_id": z["zone_id"]},
            {"$set": z},
            upsert=True,
        )
    print(f"✅ zones: upsert {zone_ids}")

    deleted_cams = db["cameras"].delete_many({"cameraId": {"$in": cam_ids}})
    db["cameras"].insert_many(docs["cameras"])
    print(
        f"✅ cameras: deleted {deleted_cams.deleted_count}, "
        f"inserted {len(docs['cameras'])}"
    )

    deleted_nodes = db["nodes"].delete_many({"node_id": {"$in": node_ids}})
    db["nodes"].insert_many(docs["nodes"])
    print(
        f"✅ nodes: deleted {deleted_nodes.deleted_count}, "
        f"inserted {len(docs['nodes'])}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed topo zone X (+ zone Y empty)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="In kế hoạch, không ghi Mongo",
    )
    args = parser.parse_args()

    db_name = settings.MONGODB_DB
    if db_name.endswith("_sandbox"):
        print(
            f"❌ MONGODB_DB='{db_name}' — dùng scripts/seed_sandbox.py cho sandbox"
        )
        return 1

    docs = build_docs()
    print(
        f"📋 topo seed → DB {db_name}: "
        f"{len(docs['cameras'])} cameras, {len(docs['nodes'])} nodes, "
        f"{len(docs['zones'])} zones (no pairs)"
    )
    print(f"   Cam9 URL: {_rtsp(9)}")
    print("   Starts A1→D9 priority:")
    for priority, code, label, cam in STARTS:
        print(f"      {priority:2d}. start_{code}  {label}  Cam{cam}")
    for code, label, cam in ENDS:
        print(f"       end. end_{code}  {label}  Cam{cam}")

    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    try:
        if not args.dry_run:
            client.admin.command("ping")
        _apply(client[db_name], docs, dry_run=args.dry_run)
    finally:
        client.close()

    if args.dry_run:
        print("\n(dry-run — chưa ghi DB)")
    else:
        print("\n✅ Done (pairs không đụng).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
