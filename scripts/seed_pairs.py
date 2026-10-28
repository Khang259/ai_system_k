"""
Seed pairs từ collection `nodes`: mọi start_* → mọi end_* (nhiều start, 1+ end).

Fetch node_id theo prefix / node_type, in pairs hợp lệ trước khi ghi.
Upsert theo (start_point, end_point) — không xoá pair khác.

    uv run python scripts/seed_pairs.py
    uv run python scripts/seed_pairs.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient, UpdateOne

from config.settings import settings


def load_start_end_from_nodes(db) -> tuple[list[str], list[str]]:
    """Đọc starts/ends từ collection nodes (node_id hoặc node_type)."""
    starts: list[str] = []
    ends: list[str] = []
    cursor = db["nodes"].find(
        {},
        {"node_id": 1, "node_type": 1},
    ).sort("node_id", 1)

    for doc in cursor:
        nid = str(doc.get("node_id") or "").strip()
        if not nid:
            continue
        ntype = str(doc.get("node_type") or "").lower()
        if ntype == "start" or nid.startswith("start_"):
            starts.append(nid)
        elif ntype == "end" or nid.startswith("end_"):
            ends.append(nid)

    starts = sorted(set(starts))
    ends = sorted(set(ends))
    return starts, ends


def build_pairs(starts: list[str], ends: list[str]) -> list[dict[str, Any]]:
    """Mỗi start ghép mỗi end — pair dispatch hợp lệ."""
    return [
        {
            "start_point": start,
            "end_point": end,
            "pair_type": "normal",
            "enabled": True,
            "auto_dispatch": True,
        }
        for start in starts
        for end in ends
    ]


def upsert_pairs(db, pairs: list[dict[str, Any]]) -> tuple[int, int]:
    ops = [
        UpdateOne(
            {"start_point": p["start_point"], "end_point": p["end_point"]},
            {"$set": p},
            upsert=True,
        )
        for p in pairs
    ]
    result = db["pairs"].bulk_write(ops, ordered=False)
    return result.upserted_count, result.modified_count


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Seed pairs tu collection nodes (nhieu start -> moi end)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uri", default=settings.MONGODB_URL)
    parser.add_argument("--db", default=settings.MONGODB_DB)
    args = parser.parse_args()

    db_name = args.db
    if db_name.endswith("_sandbox"):
        print(f"[ERR] MONGODB_DB='{db_name}' — dung seed_sandbox.py cho sandbox")
        return 1

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[db_name]

        starts, ends = load_start_end_from_nodes(db)
        if not starts or not ends:
            print(
                f"[ERR] Thieu start/end trong nodes: "
                f"starts={len(starts)} ends={len(ends)}"
            )
            return 1

        pairs = build_pairs(starts, ends)
        print(
            f"[PLAN] DB={db_name} nodes: "
            f"{len(starts)} starts x {len(ends)} ends = {len(pairs)} pairs"
        )
        print(f"   starts ({len(starts)}):")
        for s in starts:
            print(f"      - {s}")
        print(f"   ends ({len(ends)}):")
        for e in ends:
            print(f"      - {e}")
        print("   valid pairs (in truoc khi upsert):")
        for i, p in enumerate(pairs, 1):
            print(f"   {i:3d}. {p['start_point']} -> {p['end_point']}")

        if args.dry_run:
            print(f"\n(dry-run — chua ghi DB {db_name})")
            return 0

        upserted, modified = upsert_pairs(db, pairs)
    finally:
        client.close()

    print(
        f"\n[OK] DB {db_name}: upserted={upserted}, "
        f"modified={modified}, total={len(pairs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
