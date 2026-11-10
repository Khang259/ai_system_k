"""
Seed zones Line 1 / Line 2 + cam 16 + end_10000355 + pairs theo col.

Mặc định = dry-run (chỉ in preview). Ghi DB: thêm --apply

    uv run python scripts/seed_line_zones.py
    uv run python scripts/seed_line_zones.py --apply

zone_id tăng từ 1:
  1 = Line 1  → cams 8, 9, 11, 13, 14, 16
  2 = Line 2  → cams 7, 10, 12,15

Xoá zone mock cũ X/Y. Cascade nodes.zone_id theo camera.

Pairs (theo col_id trên start):
  A–F  → end_10000355
  còn lại → end_10000013
Upsert (start_point, end_point); xoá pair lệch end của cùng start.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient, UpdateOne

from config.settings import settings

ZONE_LINE1 = {"zone_id": "1", "name": "Line 1", "enabled": True}
ZONE_LINE2 = {"zone_id": "2", "name": "Line 2", "enabled": True}
OLD_MOCK_ZONE_IDS = ("X", "Y")

# Line 1 (kèm cam 15)
LINE1_CAMERA_IDS: Set[int] = {8, 9, 11, 13, 14, 15}

END_LINE2 = "end_10000355"  # cols A–F
END_LINE1 = "end_10000013"  # cols còn lại
COLS_TO_END_LINE2: Set[str] = {"A", "B", "C", "D", "E", "F"}

CAM16_ID = 16
CAM16_URL = (
    "rtsp://admin:Kortek2026#@192.168.50.126:554/Streaming/Channels/102"
)
ROI_MOCK = [0.0, 0.0, 100.0, 100.0]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _roi_end() -> dict:
    return {
        "roi": list(ROI_MOCK),
        "start": False,
        "end": True,
        "ref_width": settings.MODEL_WIDTH,
        "ref_height": settings.MODEL_HEIGHT,
    }


def _end_node_doc() -> dict:
    return {
        "node_id": END_LINE2,
        "node_type": "end",
        "zone_id": "2",
        "camera_id": CAM16_ID,
        "priority": 1,
        "enabled": True,
        "is_under_maintenance": False,
        "maintenance_reason": "",
        "lock": {"user": False, "system": False, "orderId": None},
        "updated_at": _now(),
    }


def _cam16_doc() -> dict:
    return {
        "cameraId": CAM16_ID,
        "name": "CAM-16",
        "url": CAM16_URL,
        "zone_id": "2",
        "enabled": True,
        "rois": {END_LINE2: _roi_end()},
        "updated_at": _now(),
    }


def end_for_col(col_id: str) -> str:
    """col A–F → end_10000355; cột khác → end_10000013."""
    col = str(col_id or "").strip().upper()
    if col in COLS_TO_END_LINE2:
        return END_LINE2
    return END_LINE1


def _pair_doc(start: str, end: str) -> dict:
    return {
        "start_point": start,
        "end_point": end,
        "pair_type": "normal",
        "enabled": True,
        "auto_dispatch": True,
        "updated_at": _now(),
    }


def plan_camera_zones(existing_ids: Set[int]) -> Dict[int, str]:
    """cameraId → zone_id mới."""
    assign: Dict[int, str] = {}
    for cid in LINE1_CAMERA_IDS:
        if cid in existing_ids:
            assign[cid] = "1"
    for cid in existing_ids:
        if cid in LINE1_CAMERA_IDS or cid == CAM16_ID:
            continue
        assign[cid] = "2"
    assign[CAM16_ID] = "2"
    return assign


def load_starts(db) -> List[Dict[str, Any]]:
    return list(
        db["nodes"].find(
            {"node_type": "start"},
            {
                "node_id": 1,
                "camera_id": 1,
                "zone_id": 1,
                "col_id": 1,
                "priority": 1,
                "node_name": 1,
                "_id": 0,
            },
        ).sort([("col_id", 1), ("priority", 1), ("node_id", 1)])
    )


def plan_pairs(starts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Mỗi start → đúng 1 end theo col_id."""
    planned: List[Dict[str, str]] = []
    for n in starts:
        nid = str(n.get("node_id") or "").strip()
        if not nid:
            continue
        col = str(n.get("col_id") or "").strip().upper()
        planned.append(
            {
                "start_point": nid,
                "end_point": end_for_col(col),
                "col_id": col or "<empty>",
                "camera_id": str(n.get("camera_id") or ""),
                "node_name": str(n.get("node_name") or "-"),
            }
        )
    return planned


def existing_pair_keys(db, starts: List[str]) -> Set[Tuple[str, str]]:
    if not starts:
        return set()
    cur = db["pairs"].find(
        {"start_point": {"$in": starts}},
        {"start_point": 1, "end_point": 1, "_id": 0},
    )
    return {
        (str(d.get("start_point")), str(d.get("end_point")))
        for d in cur
        if d.get("start_point") and d.get("end_point")
    }


def print_plan(
    *,
    existing_cams: List[Dict[str, Any]],
    assign: Dict[int, str],
    zones_now: List[Dict[str, Any]],
    end_exists: bool,
    cam16_exists: bool,
    planned_pairs: List[Dict[str, str]],
    pair_existing: Set[Tuple[str, str]],
) -> None:
    print("=== ZONES ===")
    print(f"  hiện có: {[(z.get('zone_id'), z.get('name')) for z in zones_now]}")
    print(
        f"  upsert:  {ZONE_LINE1['zone_id']}={ZONE_LINE1['name']}, "
        f"{ZONE_LINE2['zone_id']}={ZONE_LINE2['name']}"
    )
    print(f"  xoá mock: {list(OLD_MOCK_ZONE_IDS)}")

    print("\n=== CAMERA zone_id ===")
    by_id = {
        int(c["cameraId"]): c
        for c in existing_cams
        if c.get("cameraId") is not None
    }
    for cid in sorted(assign):
        old = (by_id.get(cid) or {}).get("zone_id")
        if old is None:
            old = "<new>" if cid == CAM16_ID else "?"
        extra = ""
        if cid == CAM16_ID:
            extra = f" [UPSERT cam16 + ROI {END_LINE2}]"
        elif cid == 15:
            extra = " [Line 1]"
        print(f"  cam {cid:2d}: {str(old):>6} → {assign[cid]}{extra}")

    print("\n=== NODE end ===")
    print(
        f"  {END_LINE2}: exists={end_exists} → upsert "
        f"zone=2 camera_id={CAM16_ID}"
    )
    print(f"  CAM16 exists={cam16_exists} url={CAM16_URL}")

    print("\n=== CASCADE nodes.zone_id ===")
    print("  theo camera_id cho mọi cam trong bảng gán ở trên")

    to_af = [p for p in planned_pairs if p["end_point"] == END_LINE2]
    to_rest = [p for p in planned_pairs if p["end_point"] == END_LINE1]
    print(
        f"\n=== PAIRS (col A–F → {END_LINE2}; "
        f"còn lại → {END_LINE1}) ==="
    )
    print(f"  A–F: {len(to_af)} | còn lại: {len(to_rest)} | tổng: {len(planned_pairs)}")

    upsert_new = 0
    already = 0
    stale = 0
    for p in planned_pairs:
        key = (p["start_point"], p["end_point"])
        wrong_end = END_LINE1 if p["end_point"] == END_LINE2 else END_LINE2
        has_stale = (p["start_point"], wrong_end) in pair_existing
        if has_stale:
            stale += 1
        if key in pair_existing:
            already += 1
            status = "OK"
        else:
            upsert_new += 1
            status = "UPSERT"
        print(
            f"  [{status:6}] col={p['col_id']:7} cam{p['camera_id']:>2} "
            f"{p['start_point']} → {p['end_point']}"
            + ("  (+xoá end lệch)" if has_stale else "")
        )
    print(
        f"  tóm tắt: upsert_mới≈{upsert_new}, đã_đúng={already}, "
        f"có_pair_lệch_sẽ_xoá≈{stale}"
    )


def apply_pairs(db, planned_pairs: List[Dict[str, str]]) -> None:
    pairs = db["pairs"]
    pair_docs = [
        _pair_doc(p["start_point"], p["end_point"]) for p in planned_pairs
    ]
    if not pair_docs:
        print("pairs: không có start — bỏ qua")
        return

    ops = [
        UpdateOne(
            {"start_point": p["start_point"], "end_point": p["end_point"]},
            {"$set": p},
            upsert=True,
        )
        for p in pair_docs
    ]
    r = pairs.bulk_write(ops, ordered=False)
    print(
        f"pairs upserted: upserted={r.upserted_count} "
        f"modified={r.modified_count}"
    )

    # Xoá pair cùng start nhưng sai end (A–F không còn gắn end_10000013, …)
    deleted = 0
    for p in planned_pairs:
        wrong = END_LINE1 if p["end_point"] == END_LINE2 else END_LINE2
        res = pairs.delete_one(
            {"start_point": p["start_point"], "end_point": wrong}
        )
        deleted += res.deleted_count
    print(f"pairs stale deleted: {deleted}")


def apply(
    db,
    *,
    assign: Dict[int, str],
    planned_pairs: List[Dict[str, str]],
) -> None:
    zones = db["zones"]
    cams = db["cameras"]
    nodes = db["nodes"]

    for z in (ZONE_LINE1, ZONE_LINE2):
        zones.update_one({"zone_id": z["zone_id"]}, {"$set": z}, upsert=True)
    print("zones upserted: 1=Line 1, 2=Line 2")

    del_z = zones.delete_many({"zone_id": {"$in": list(OLD_MOCK_ZONE_IDS)}})
    print(f"zones deleted (mock X/Y): {del_z.deleted_count}")

    del_mock = cams.delete_many({"name": {"$regex": "^MOCK-CAM-"}})
    print(f"mock cameras deleted: {del_mock.deleted_count}")

    cam_ops = [
        UpdateOne(
            {"cameraId": cid},
            {"$set": {"zone_id": zid, "updated_at": _now()}},
        )
        for cid, zid in assign.items()
        if cid != CAM16_ID
    ]
    if cam_ops:
        r = cams.bulk_write(cam_ops, ordered=False)
        print(
            f"cameras zone updated: matched={r.matched_count} "
            f"modified={r.modified_count}"
        )

    cams.update_one({"cameraId": CAM16_ID}, {"$set": _cam16_doc()}, upsert=True)
    print(f"camera {CAM16_ID} upserted (zone=2, ROI {END_LINE2})")

    nodes.update_one(
        {"node_id": END_LINE2}, {"$set": _end_node_doc()}, upsert=True
    )
    print(f"node {END_LINE2} upserted")

    cascaded = 0
    for cid, zid in assign.items():
        r = nodes.update_many(
            {"camera_id": cid},
            {"$set": {"zone_id": zid, "updated_at": _now()}},
        )
        cascaded += r.modified_count
    print(f"nodes zone cascaded: {cascaded}")

    apply_pairs(db, planned_pairs)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Seed Line 1 / Line 2 zones")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ghi Mongo (mặc định chỉ dry-run / preview)",
    )
    args = parser.parse_args()

    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[settings.MONGODB_DB]

    existing_cams = list(
        db["cameras"].find(
            {}, {"cameraId": 1, "zone_id": 1, "name": 1, "url": 1}
        )
    )
    existing_ids = {
        int(c["cameraId"])
        for c in existing_cams
        if c.get("cameraId") is not None
    }
    assign = plan_camera_zones(existing_ids)
    zones_now = list(db["zones"].find({}, {"zone_id": 1, "name": 1, "_id": 0}))
    end_exists = db["nodes"].find_one({"node_id": END_LINE2}) is not None
    cam16_exists = db["cameras"].find_one({"cameraId": CAM16_ID}) is not None
    starts = load_starts(db)
    planned_pairs = plan_pairs(starts)
    start_ids = [p["start_point"] for p in planned_pairs]
    pair_existing = existing_pair_keys(db, start_ids)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"DB={settings.MONGODB_DB}  mode={mode}\n")
    print_plan(
        existing_cams=existing_cams,
        assign=assign,
        zones_now=zones_now,
        end_exists=end_exists,
        cam16_exists=cam16_exists,
        planned_pairs=planned_pairs,
        pair_existing=pair_existing,
    )

    if not args.apply:
        print("\n[DRY-RUN] Không ghi DB. Chạy lại với --apply khi OK.")
        return 0

    apply(db, assign=assign, planned_pairs=planned_pairs)
    print("\n[DONE] Đã ghi DB. Restart runtime để CameraManager nạp zone mới.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
