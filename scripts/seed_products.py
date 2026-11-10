"""
Append seed cột I/K (UpdateMap) vào zone X — KHÔNG xoá cameras/pairs cũ.

    # xem bảng seed + kế hoạch insert/patch (không ghi DB)
    uv run python scripts/seed_products.py --dry-run

    # ghi Mongo: insert bản ghi chưa có + patch node_name nếu lệch; cần --yes
    uv run python scripts/seed_products.py --yes

Priority tiếp từ 73 (sau F/G/H = 46..72). End end_10000013 đã có — không insert lại.
Cam 7/10/12: insert nếu chưa có. ROI để trống — vẽ sau trên FE.
Node đã có: chỉ $set node_name khi khác mapping (không đè field khác).
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Windows console (cp1252) khong in duoc tieng Viet / emoji
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient, UpdateOne

from config.settings import settings

ZONE_ID = "X"
END_NODE = "end_10000013"
PRIORITY_START = 73

RTSP_USER = "admin"
RTSP_PASS = "Kortek2026#"
RTSP_PORT = 554
RTSP_PATH = "/Streaming/Channels/102"
IP_BASE = "192.168.50"

# Cameras chỉ insert nếu chưa có
NEW_CAMERA_IDS = (7, 10, 12)

# (suffix topo, col_id, camera_id) — thứ tự I → K theo UpdateMap.xlsx
# node_id = start_10000{suffix:03d}; priority = PRIORITY_START + index
# Excel col I1..I9 / K1..K9 → col_id = I/K, node_name = I1..K9
UPDATE_MAP_SEQ: list[tuple[int, str, int]] = [
    (314, "I", 7),
    (316, "I", 7),
    (317, "I", 7),
    (319, "I", 10),
    (321, "I", 10),
    (323, "I", 10),
    (325, "I", 12),
    (327, "I", 12),
    (329, "I", 12),
    (332, "K", 7),
    (334, "K", 7),
    (335, "K", 7),
    (337, "K", 10),
    (339, "K", 10),
    (341, "K", 10),
    (343, "K", 12),
    (345, "K", 12),
    (347, "K", 12),
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
    node_id: str,
    camera_id: int,
    priority: int,
    col_id: str,
    node_name: str,
) -> dict:
    return {
        "node_id": node_id,
        "node_type": "start",
        "zone_id": ZONE_ID,
        "camera_id": camera_id,
        "priority": priority,
        "col_id": col_id,
        "node_name": node_name,
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
    starts: list[tuple[int, str, str, int, str]] = []
    rank_by_col: dict[str, int] = defaultdict(int)
    for i, (suffix, col_id, camera_id) in enumerate(UPDATE_MAP_SEQ):
        priority = PRIORITY_START + i
        rank_by_col[col_id] += 1
        label = f"{col_id}{rank_by_col[col_id]}"
        starts.append(
            (priority, _start_node_id(suffix), col_id, camera_id, label)
        )

    nodes = [
        _node_doc(nid, cam, pri, col, name)
        for pri, nid, col, cam, name in starts
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
        for _, nid, _, _, _ in starts
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
        f"\n{'#':>2} {'prio':>4} {'node_name':9} {'col':3} {'node_id':22} "
        f"{'cam':>3}  pair_end"
    )
    for i, (pri, nid, col, cam, name) in enumerate(docs["_starts"], start=1):
        print(
            f"{i:2d} {pri:4d} {name:9} {col:3} {nid:22} "
            f"{cam:3d}  {END_NODE}"
        )

    by_cam: dict[int, list[str]] = defaultdict(list)
    for pri, nid, col, cam, label in docs["_starts"]:
        by_cam[cam].append(f"P{pri}:{label}:{nid}")

    print("\nRTSP / nodes theo camera:")
    all_cams = sorted({cam for _, _, _, cam, _ in docs["_starts"]})
    for cid in all_cams:
        tag = "NEW" if cid in NEW_CAMERA_IDS else "SKIP(exist)"
        print(f"  cam {cid:2d}  [{tag}]  {_rtsp_url(cid)}")
        for item in by_cam[cid]:
            print(f"           -> {item}")


def _node_name_patches(
    db, docs: dict
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Trả (to_insert, to_patch, name_ok). to_patch: node_id/existing/proposed."""
    desired = {n["node_id"]: n for n in docs["nodes"]}
    found = list(
        db["nodes"].find(
            {"node_id": {"$in": list(desired.keys())}},
            {"node_id": 1, "node_name": 1},
        )
    )
    by_id = {str(d["node_id"]): d for d in found}

    to_insert: list[dict[str, Any]] = []
    to_patch: list[dict[str, Any]] = []
    name_ok: list[str] = []
    for nid, node in desired.items():
        doc = by_id.get(nid)
        if not doc:
            to_insert.append(node)
            continue
        existing = str(doc.get("node_name") or "")
        proposed = str(node.get("node_name") or "")
        if existing != proposed:
            to_patch.append(
                {"node_id": nid, "existing": existing, "proposed": proposed}
            )
        else:
            name_ok.append(nid)
    return to_insert, to_patch, name_ok


def _print_db_plan(
    cams_new: int,
    cams_skip: int,
    to_insert: list[dict[str, Any]],
    to_patch: list[dict[str, Any]],
    name_ok: list[str],
    pairs_new: int,
    pairs_skip: int,
) -> None:
    print(
        f"\n[PLAN] cameras: insert={cams_new} skip={cams_skip}"
    )
    print(
        f"[PLAN] nodes: insert={len(to_insert)} "
        f"patch_node_name={len(to_patch)} name_ok={len(name_ok)}"
    )
    print(f"[PLAN] pairs: insert={pairs_new} skip={pairs_skip}")
    if to_patch:
        print(f"\n{'node_id':22} {'existing':10} {'proposed':10}")
        print("-" * 46)
        for row in to_patch:
            print(
                f"{row['node_id']:22} "
                f"{row['existing'] or '(empty)':10} "
                f"{row['proposed']:10}"
            )


def _apply(db, docs: dict, dry_run: bool) -> None:
    """Insert bản ghi mới + patch node_name cho node đã có nếu lệch."""
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

    to_insert, to_patch, name_ok = _node_name_patches(db, docs)

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

    _print_db_plan(
        len(cams_to_insert),
        len(docs["cameras"]) - len(cams_to_insert),
        to_insert,
        to_patch,
        name_ok,
        len(pairs_to_insert),
        len(docs["pairs"]) - len(pairs_to_insert),
    )

    if dry_run:
        print("\n(dry-run — chua ghi Mongo)")
        return

    if cams_to_insert:
        db["cameras"].insert_many(cams_to_insert)
    print(
        f"[ok] cameras: insert {len(cams_to_insert)} "
        f"(skip {len(docs['cameras']) - len(cams_to_insert)})"
    )

    if to_insert:
        db["nodes"].insert_many(to_insert)
    print(f"[ok] nodes: insert {len(to_insert)}")

    if to_patch:
        ops = [
            UpdateOne(
                {"node_id": row["node_id"], "node_type": "start"},
                {"$set": {"node_name": row["proposed"]}},
            )
            for row in to_patch
        ]
        result = db["nodes"].bulk_write(ops, ordered=False)
        print(
            f"[ok] nodes: patch node_name matched={result.matched_count} "
            f"modified={result.modified_count} ops={len(ops)}"
        )
    else:
        print("[ok] nodes: patch node_name 0")

    if name_ok:
        print(f"[ok] nodes: node_name already ok={len(name_ok)}")

    if pairs_to_insert:
        db["pairs"].insert_many(pairs_to_insert)
    print(
        f"[ok] pairs: insert {len(pairs_to_insert)} "
        f"(skip {len(docs['pairs']) - len(pairs_to_insert)})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append seed cột I/K (UpdateMap) vào zone X"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="In bảng seed + kế hoạch insert/patch, không ghi DB",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Xác nhận ghi DB (bắt buộc nếu không --dry-run)",
    )
    args = parser.parse_args()

    docs = build_docs()
    _print_summary(docs)

    if not args.dry_run and not args.yes:
        print("\n[!] Can --yes de ghi DB (hoac --dry-run de xem).")
        return 1

    db_name = settings.MONGODB_DB
    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[db_name]

    mode = "DRY-RUN" if args.dry_run else "APPEND+PATCH node_name"
    print(f"\nDB=`{db_name}`  mode={mode}")
    _apply(db, docs, dry_run=args.dry_run)

    client.close()
    if not args.dry_run:
        print(f"\n[ok] Append/patch I/K xong -> DB `{db_name}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
