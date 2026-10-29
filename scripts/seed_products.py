"""
Append seed cột F/G/H (Khang) vào zone X — KHÔNG xoá / đè dữ liệu cũ.

    # xem docs sẽ insert (không ghi DB)
    uv run python scripts/seed_products.py --dry-run

    # ghi Mongo (chỉ insert bản ghi chưa có; cần --yes)
    uv run python scripts/seed_products.py --yes

Priority tiếp từ 46 (sau A–E). End end_10000013 đã có — không insert lại.
Cam mới: 7, 10, 12. Cam 8/11/13 đã có — giữ ROI.
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
END_NODE = "end_10000013"
PRIORITY_START = 46

RTSP_USER = "admin"
RTSP_PASS = "Kortek2026#"
RTSP_PORT = 554
RTSP_PATH = "/Streaming/Channels/102"
IP_BASE = "192.168.50"

# Cameras chỉ insert nếu chưa có (8/11/13 đã có ROI — skip)
NEW_CAMERA_IDS = (7, 10, 12)

# (suffix topo, col_id, camera_id) — thứ tự F → G → H
# node_id = start_10000{suffix:03d}; priority = PRIORITY_START + index
KHANG_SEQ: list[tuple[int, str, int]] = [
    (118, "F", 8),
    (121, "F", 8),
    (124, "F", 8),
    (127, "F", 11),
    (130, "F", 11),
    (133, "F", 11),
    (136, "F", 13),
    (139, "F", 13),
    (142, "F", 13),
    (257, "G", 7),
    (260, "G", 7),
    (264, "G", 7),
    (267, "G", 10),
    (270, "G", 10),
    (273, "G", 10),
    (276, "G", 12),
    (279, "G", 12),
    (282, "G", 12),
    (285, "H", 7),
    (287, "H", 7),
    (288, "H", 7),
    (290, "H", 10),
    (292, "H", 10),
    (294, "H", 10),
    (296, "H", 12),
    (298, "H", 12),
    (300, "H", 12),
]


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
    node_id: str, camera_id: int, priority: int, col_id: str
) -> dict:
    return {
        "node_id": node_id,
        "node_type": "start",
        "zone_id": ZONE_ID,
        "camera_id": camera_id,
        "priority": priority,
        "col_id": col_id,
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
    starts: list[tuple[int, str, str, int]] = []
    for i, (suffix, col_id, camera_id) in enumerate(KHANG_SEQ):
        priority = PRIORITY_START + i
        starts.append(
            (priority, _start_node_id(suffix), col_id, camera_id)
        )

    nodes = [
        _node_doc(nid, cam, pri, col) for pri, nid, col, cam in starts
    ]
    cameras = [_camera_doc(cid) for cid in NEW_CAMERA_IDS]
    pairs = [
        {
            "start_point": nid,
            "end_point": END_NODE,
            "pair_type": "normal",
            "enabled": True,
            "auto_dispatch": True,
        }
        for _, nid, _, _ in starts
    ]
    return {
        "cameras": cameras,
        "nodes": nodes,
        "pairs": pairs,
        "_starts": starts,
    }


def _print_summary(docs: dict) -> None:
    print(f"zone={ZONE_ID}  end={END_NODE} (reuse, khong insert)")
    print(
        f"cameras_new={len(docs['cameras'])}  "
        f"nodes={len(docs['nodes'])}  pairs={len(docs['pairs'])}"
    )
    print(
        f"\n{'#':>2} {'prio':>4} {'col':3} {'node_id':22} "
        f"{'cam':>3}  pair_end"
    )
    for i, (pri, nid, col, cam) in enumerate(docs["_starts"], start=1):
        print(f"{i:2d} {pri:4d} {col:3} {nid:22} {cam:3d}  {END_NODE}")

    by_cam: dict[int, list[str]] = defaultdict(list)
    for pri, nid, col, cam in docs["_starts"]:
        by_cam[cam].append(f"P{pri}:{col}:{nid}")

    print("\nRTSP / nodes theo camera:")
    all_cams = sorted({cam for *_, cam in docs["_starts"]})
    for cid in all_cams:
        tag = "NEW" if cid in NEW_CAMERA_IDS else "SKIP(exist)"
        print(f"  cam {cid:2d}  [{tag}]  {_rtsp_url(cid)}")
        for item in by_cam[cid]:
            print(f"           -> {item}")


def _append_only(db, docs: dict) -> None:
    """Chỉ insert bản ghi chưa có — không xoá / không đè."""
    existing_cams = {
        d["cameraId"]
        for d in db["cameras"].find(
            {"cameraId": {"$in": list(NEW_CAMERA_IDS)}},
            {"cameraId": 1},
        )
    }
    cams_to_insert = [
        c for c in docs["cameras"] if c["cameraId"] not in existing_cams
    ]
    if cams_to_insert:
        db["cameras"].insert_many(cams_to_insert)
    print(
        f"[ok] cameras: insert {len(cams_to_insert)} "
        f"(skip {len(docs['cameras']) - len(cams_to_insert)})"
    )

    node_ids = [n["node_id"] for n in docs["nodes"]]
    existing_nodes = {
        d["node_id"]
        for d in db["nodes"].find(
            {"node_id": {"$in": node_ids}}, {"node_id": 1}
        )
    }
    nodes_to_insert = [
        n for n in docs["nodes"] if n["node_id"] not in existing_nodes
    ]
    if nodes_to_insert:
        db["nodes"].insert_many(nodes_to_insert)
    print(
        f"[ok] nodes: insert {len(nodes_to_insert)} "
        f"(skip {len(docs['nodes']) - len(nodes_to_insert)})"
    )

    start_ids = [p["start_point"] for p in docs["pairs"]]
    existing_pairs = {
        d["start_point"]
        for d in db["pairs"].find(
            {
                "start_point": {"$in": start_ids},
                "end_point": END_NODE,
            },
            {"start_point": 1},
        )
    }
    pairs_to_insert = [
        p for p in docs["pairs"] if p["start_point"] not in existing_pairs
    ]
    if pairs_to_insert:
        db["pairs"].insert_many(pairs_to_insert)
    print(
        f"[ok] pairs: insert {len(pairs_to_insert)} "
        f"(skip {len(docs['pairs']) - len(pairs_to_insert)})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append seed cột F/G/H (Khang) vào zone X"
    )
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

    print(f"\nDB=`{db_name}`  mode=APPEND (no purge)")
    _append_only(db, docs)

    client.close()
    print(f"\n[ok] Append F/G/H xong -> DB `{db_name}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
