"""
Gán col_id cho start nodes theo mapping hiện trường.

Mặc định = dry-run (chỉ in bảng kiểm tra, KHÔNG ghi DB).
Khi đã OK: thêm --apply để update.

    uv run python scripts/migrate_assign_col_id.py
    uv run python scripts/migrate_assign_col_id.py --apply

Format node_id: giống seed_cam_nodes — suffix → start_10000{xxx}
(cN) = camera_id kỳ vọng (đối chiếu với DB, không ghi camera).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient, UpdateOne

from config.settings import settings

# (suffix, camera_id_kỳ_vọng) theo thứ tự trong col (đầu hàng → cuối)
# Col A–E — user cung cấp 2026-10-28
COL_MAP: Dict[str, List[Tuple[str, int]]] = {
    "A": [
        ("146", 9),
        ("151", 9),
        ("154", 9),
        ("157", 9),
        ("163", 9),
        ("160", 14),
        ("166", 14),
        ("169", 14),
        ("172", 14),
    ],
    "B": [
        ("177", 9),
        ("180", 9),
        ("183", 9),
        ("186", 9),
        ("189", 9),
        ("193", 14),
        ("196", 14),
        ("199", 14),
        ("202", 14),
    ],
    "C": [
        ("205", 8),
        ("208", 8),
        ("211", 8),
        ("214", 11),
        ("217", 11),
        ("220", 11),
        ("223", 13),
        ("226", 13),
        ("229", 13),
    ],
    "D": [
        ("057", 8),
        ("056", 8),
        ("069", 8),
        ("073", 11),
        ("076", 11),
        ("081", 11),
        ("084", 13),
        ("087", 13),
        ("090", 13),
    ],
    "E": [
        ("059", 8),
        ("058", 8),
        ("093", 8),
        ("096", 11),
        ("100", 11),
        ("103", 11),
        ("106", 13),
        ("109", 13),
        ("112", 13),
    ],
}


def _code(suffix: str) -> str:
    """'57'/'057' → '10000057', '146' → '10000146', '100' → '10000100'."""
    s = suffix.lstrip("0") or "0"
    if len(s) <= 3:
        return f"10000{s.zfill(3)}"
    return f"1000{s.zfill(4)}"


def _start_id(suffix: str) -> str:
    return f"start_{_code(suffix)}"


def _build_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for col_id, items in COL_MAP.items():
        for order, (suffix, cam) in enumerate(items, start=1):
            rows.append(
                {
                    "col_id": col_id,
                    "order_in_col": order,
                    "suffix": suffix,
                    "node_id": _start_id(suffix),
                    "expect_camera_id": cam,
                }
            )
    return rows


def _print_table(rows: List[Dict[str, Any]], db_by_id: Dict[str, Dict[str, Any]]) -> None:
    print("=" * 100)
    print(
        f"{'col':3} {'#':>2} {'suffix':>5} {'node_id':22} "
        f"{'cam?':>5} {'db_cam':>6} {'db_zone':8} {'db_prio':>7} {'db_col':6} {'status'}"
    )
    print("-" * 100)
    ok = missing = cam_mismatch = 0
    for r in rows:
        nid = r["node_id"]
        doc = db_by_id.get(nid)
        if not doc:
            status = "MISSING_IN_DB"
            missing += 1
            db_cam = db_zone = db_prio = db_col = "-"
        else:
            db_cam = doc.get("camera_id")
            db_zone = doc.get("zone_id") or ""
            db_prio = doc.get("priority")
            db_col = doc.get("col_id") if doc.get("col_id") not in (None, "") else ""
            if db_cam is not None and int(db_cam) != int(r["expect_camera_id"]):
                status = "CAM_MISMATCH"
                cam_mismatch += 1
            else:
                status = "OK"
                ok += 1
        print(
            f"{r['col_id']:3} {r['order_in_col']:2d} {r['suffix']:>5} {nid:22} "
            f"{r['expect_camera_id']:5d} {str(db_cam):>6} {str(db_zone):8} "
            f"{str(db_prio):>7} {str(db_col):6} {status}"
        )
    print("-" * 100)
    print(
        f"total={len(rows)}  ok={ok}  missing={missing}  cam_mismatch={cam_mismatch}"
    )
    print("=" * 100)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Gán col_id cho start nodes (default: dry-run)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ghi col_id vào Mongo (mặc định chỉ in bảng)",
    )
    parser.add_argument(
        "--allow-cam-mismatch",
        action="store_true",
        help="Vẫn update khi camera_id DB khác mapping (cảnh báo)",
    )
    args = parser.parse_args()

    rows = _build_rows()
    node_ids = [r["node_id"] for r in rows]

    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[settings.MONGODB_DB]
    found = list(
        db["nodes"].find(
            {"node_id": {"$in": node_ids}},
            {
                "node_id": 1,
                "camera_id": 1,
                "zone_id": 1,
                "priority": 1,
                "col_id": 1,
                "node_type": 1,
            },
        )
    )
    db_by_id = {str(d["node_id"]): d for d in found}

    print(f"DB={settings.MONGODB_DB}  mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Mapping: {len(rows)} starts → cols {sorted(COL_MAP.keys())}\n")
    _print_table(rows, db_by_id)

    # Sample preview: 3 đầu mỗi col
    print("\n--- Sample (3 đầu mỗi col) ---")
    for col_id, items in COL_MAP.items():
        sample = items[:3]
        parts = [
            f"{_start_id(s)} (cam{c}→col {col_id})" for s, c in sample
        ]
        print(f"  Col {col_id}: " + " → ".join(parts))

    if not args.apply:
        print(
            "\n[DRY-RUN] Chưa ghi DB. Kiểm tra bảng trên; "
            "nếu đúng chạy lại với --apply"
        )
        return 0

    ops: List[UpdateOne] = []
    skipped: List[str] = []
    for r in rows:
        nid = r["node_id"]
        doc = db_by_id.get(nid)
        if not doc:
            skipped.append(f"{nid}: missing")
            continue
        db_cam = doc.get("camera_id")
        if (
            db_cam is not None
            and int(db_cam) != int(r["expect_camera_id"])
            and not args.allow_cam_mismatch
        ):
            skipped.append(
                f"{nid}: cam DB={db_cam} expect={r['expect_camera_id']}"
            )
            continue
        ops.append(
            UpdateOne(
                {"node_id": nid, "node_type": "start"},
                {"$set": {"col_id": r["col_id"]}},
            )
        )

    if skipped:
        print(f"\nSkipped ({len(skipped)}):")
        for s in skipped:
            print(f"  - {s}")

    if not ops:
        print("\n[APPLY] Không có update nào.")
        return 1 if skipped else 0

    result = db["nodes"].bulk_write(ops, ordered=False)
    print(
        f"\n[APPLY] matched={result.matched_count} "
        f"modified={result.modified_count} ops={len(ops)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
