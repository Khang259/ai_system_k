"""
Seed zone X: 45 start + 1 end + 6 cameras + 45 pairs.

Chỉ xoá/ghi dữ liệu liên quan zone X (và cameraId trong danh sách),
không wipe toàn bộ collection.

    # xem docs sẽ insert (không ghi DB)
    uv run python scripts/seed_zone_x.py --dry-run

    # ghi Mongo (cần --yes)
    uv run python scripts/seed_zone_x.py --yes

Node id = start_/end_ + content topo (vd. 146 → start_10000146).
IP = 192.168.50.{100 + cameraId}  (cam 1 → .111).
ROI để trống — vẽ sau trên FE.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

# Windows console (cp1252) khong in duoc tieng Viet / emoji
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings

ZONE_ID = "X"
ZONE_NAME = "Zone X"
END_NODE = "end_10000013"
END_CAMERA_ID = 15

RTSP_USER = "admin"
RTSP_PASS = "Kortek2026#"
RTSP_PORT = 554
RTSP_PATH = "/Streaming/Channels/102"
IP_BASE = "192.168.50"

# (suffix 3 số topo, cameraId) — priority = index + 1
START_SEQ: list[tuple[int, int]] = [
    (146, 9),
    (151, 9),
    (154, 9),
    (157, 9),
    (163, 9),
    (160, 14),
    (166, 14),
    (169, 14),
    (172, 14),
    (177, 9),
    (180, 9),
    (183, 9),
    (186, 9),
    (189, 9),
    (193, 14),
    (196, 14),
    (199, 14),
    (202, 14),
    (205, 8),
    (208, 8),
    (211, 8),
    (214, 11),
    (217, 11),
    (220, 11),
    (223, 13),
    (226, 13),
    (229, 13),
    (57, 8),
    (56, 8),
    (69, 8),
    (73, 11),
    (76, 11),
    (81, 11),
    (84, 13),
    (87, 13),
    (90, 13),
    (59, 8),
    (58, 8),
    (93, 8),
    (96, 11),
    (100, 11),
    (103, 11),
    (106, 13),
    (109, 13),
    (112, 13),
]

COLLECTIONS = ("zones", "cameras", "nodes", "pairs")


def _start_node_id(suffix: int) -> str:
    return f"start_10000{suffix:03d}"


def _camera_ip(camera_id: int) -> str:
    return f"{IP_BASE}.{110 + camera_id}"


def _rtsp_url(camera_id: int) -> str:
    return (
        f"rtsp://{RTSP_USER}:{RTSP_PASS}@"
        f"{_camera_ip(camera_id)}:{RTSP_PORT}{RTSP_PATH}"
    )


def _node_doc(
    node_id: str, node_type: str, camera_id: int, priority: int
) -> dict:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "zone_id": ZONE_ID,
        "camera_id": camera_id,
        "priority": priority,
        "enabled": True,
        "is_under_maintenance": False,
        "maintenance_reason": "",
        "lock": {"user": False, "system": False, "orderId": None},
    }


def _camera_doc(camera_id: int) -> dict:
    return {
        "cameraId": camera_id,
        "name": f"CAM-{camera_id:02d}",
        "url": _rtsp_url(camera_id),
        "zone_id": ZONE_ID,
        "enabled": True,
        "rois": {},
    }


def build_docs() -> dict:
    starts: list[tuple[int, str, int]] = []
    for priority, (suffix, camera_id) in enumerate(START_SEQ, start=1):
        starts.append((priority, _start_node_id(suffix), camera_id))

    nodes = [
        _node_doc(nid, "start", cam, pri) for pri, nid, cam in starts
    ]
    nodes.append(_node_doc(END_NODE, "end", END_CAMERA_ID, 1))

    camera_ids = sorted({cam for _, _, cam in starts} | {END_CAMERA_ID})
    cameras = [_camera_doc(cid) for cid in camera_ids]

    pairs = [
        {
            "start_point": nid,
            "end_point": END_NODE,
            "pair_type": "normal",
            "enabled": True,
            "auto_dispatch": True,
        }
        for _, nid, _ in starts
    ]

    zones = [{"zone_id": ZONE_ID, "name": ZONE_NAME, "enabled": True}]
    return {
        "zones": zones,
        "cameras": cameras,
        "nodes": nodes,
        "pairs": pairs,
        "_starts": starts,
        "_camera_ids": camera_ids,
    }


def _print_summary(docs: dict) -> None:
    by_cam: dict[int, list[str]] = defaultdict(list)
    for pri, nid, cam in docs["_starts"]:
        by_cam[cam].append(f"P{pri}:{nid}")

    print(f"zone={ZONE_ID}  end={END_NODE} (cam {END_CAMERA_ID})")
    print(f"cameras={len(docs['cameras'])}  nodes={len(docs['nodes'])}  "
          f"pairs={len(docs['pairs'])}")
    print("\nRTSP / nodes theo camera:")
    for cid in docs["_camera_ids"]:
        print(f"  cam {cid:2d}  {_rtsp_url(cid)}")
        if cid == END_CAMERA_ID:
            print(f"           -> {END_NODE}")
        else:
            for item in by_cam[cid]:
                print(f"           -> {item}")


def _purge_zone(db) -> None:
    """Xoá dữ liệu cũ của zone X + camera/pair liên quan trước khi insert."""
    start_ids = [_start_node_id(s) for s, _ in START_SEQ]
    camera_ids = sorted({c for _, c in START_SEQ} | {END_CAMERA_ID})

    db["zones"].delete_many({"zone_id": ZONE_ID})
    db["cameras"].delete_many(
        {"$or": [{"zone_id": ZONE_ID}, {"cameraId": {"$in": camera_ids}}]}
    )
    db["nodes"].delete_many(
        {
            "$or": [
                {"zone_id": ZONE_ID},
                {"node_id": {"$in": start_ids + [END_NODE]}},
                {"camera_id": {"$in": camera_ids}},
            ]
        }
    )
    db["pairs"].delete_many(
        {
            "$or": [
                {"start_point": {"$in": start_ids}},
                {"end_point": END_NODE},
            ]
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed zone X vào MongoDB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ in bảng seed, không ghi DB",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Xác nhận ghi DB (bắt buộc nếu không --dry-run)",
    )
    args = parser.parse_args()

    docs = build_docs()
    _print_summary(docs)

    if args.dry_run:
        print("\n(dry-run — chua ghi Mongo)")
        return 0

    if not args.yes:
        print("\n[!] Can --yes de ghi DB (hoac --dry-run de xem).")
        return 1

    db_name = settings.MONGODB_DB
    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[db_name]

    _purge_zone(db)
    for name in COLLECTIONS:
        db[name].insert_many(docs[name])
        print(f"[ok] {name}: {len(docs[name])}")

    client.close()
    print(f"\n[ok] Seed zone {ZONE_ID} xong -> DB `{db_name}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
