"""
Gán node_name cho start nodes: {col_id}{rank}.

rank = thứ tự trong cùng zone + col, sort priority ASC (không lấy priority toàn cục).
Ví dụ: col A priority 1 → A1; col B priority 10 (đầu cột) → B1.

Mặc định = dry-run (chỉ in bảng). Khi đã OK: --apply.

    uv run python scripts/migrate_seed_node_name.py
    uv run python scripts/migrate_seed_node_name.py --apply

End nodes: bỏ qua (không có col_id theo quy ước hiện trường).
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient, UpdateOne

from config.settings import settings


def _build_proposals(
    starts: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Trả (proposals, missing_col)."""
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    missing: List[Dict[str, Any]] = []
    for doc in starts:
        col = str(doc.get("col_id") or "").strip()
        if not col:
            missing.append(doc)
            continue
        zone = str(doc.get("zone_id") or "")
        grouped[(zone, col)].append(doc)

    proposals: List[Dict[str, Any]] = []
    for zone, col in sorted(grouped.keys(), key=lambda x: (x[0], x[1])):
        rows = sorted(
            grouped[(zone, col)],
            key=lambda d: (
                int(d.get("priority") or 0),
                str(d.get("node_id") or ""),
            ),
        )
        for rank, doc in enumerate(rows, start=1):
            name = f"{col}{rank}"
            proposals.append(
                {
                    "zone_id": zone,
                    "col_id": col,
                    "rank": rank,
                    "priority": int(doc.get("priority") or 0),
                    "node_id": str(doc.get("node_id") or ""),
                    "camera_id": doc.get("camera_id"),
                    "existing": doc.get("node_name") or "",
                    "proposed": name,
                }
            )
    return proposals, missing


def _print_table(proposals: List[Dict[str, Any]]) -> None:
    print(
        f"{'zone':4} {'col':3} {'rank':>4} {'priority':>8} "
        f"{'node_id':22} {'camera':>6} {'proposed':>10} {'existing':>10}"
    )
    print("-" * 90)
    for r in proposals:
        print(
            f"{r['zone_id']:4} {r['col_id']:3} {r['rank']:4d} {r['priority']:8d} "
            f"{r['node_id']:22} {str(r['camera_id'] or ''):>6} "
            f"{r['proposed']:>10} {str(r['existing']):>10}"
        )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Gán node_name = col+rank cho start nodes (default: dry-run)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ghi node_name vào Mongo (mặc định chỉ in bảng)",
    )
    args = parser.parse_args()

    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[settings.MONGODB_DB]
    starts = list(
        db["nodes"].find(
            {"node_type": "start"},
            {
                "node_id": 1,
                "zone_id": 1,
                "col_id": 1,
                "priority": 1,
                "camera_id": 1,
                "node_name": 1,
                "_id": 0,
            },
        )
    )

    proposals, missing = _build_proposals(starts)
    unchanged = sum(1 for r in proposals if r["existing"] == r["proposed"])
    to_write = [r for r in proposals if r["existing"] != r["proposed"]]

    print(f"DB={settings.MONGODB_DB}  mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print(
        f"starts={len(starts)} proposed={len(proposals)} "
        f"to_write={len(to_write)} unchanged={unchanged} "
        f"missing_col={len(missing)}\n"
    )
    _print_table(proposals)

    if missing:
        print(f"\n--- starts missing col_id ({len(missing)}) — bỏ qua ---")
        for d in sorted(missing, key=lambda x: str(x.get("node_id") or "")):
            print(f"  {d.get('node_id')} zone={d.get('zone_id')} priority={d.get('priority')}")

    if not args.apply:
        print(
            "\n[DRY-RUN] Chưa ghi DB. Kiểm tra bảng trên; "
            "nếu đúng chạy lại với --apply"
        )
        return 0

    if not to_write:
        print("\n[APPLY] Không có thay đổi nào.")
        return 0

    now = datetime.now(timezone.utc)
    ops = [
        UpdateOne(
            {"node_id": r["node_id"], "node_type": "start"},
            {"$set": {"node_name": r["proposed"], "updated_at": now}},
        )
        for r in to_write
    ]
    result = db["nodes"].bulk_write(ops, ordered=False)
    print(
        f"\n[APPLY] matched={result.matched_count} "
        f"modified={result.modified_count} ops={len(ops)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
