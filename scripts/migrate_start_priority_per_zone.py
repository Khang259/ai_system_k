"""
Migrate start.priority: unique trong từng zone (1..N).

Thứ tự gán trong zone: digits trong node_id ASC (giữ gần hành vi sort cũ),
rồi node_id. End không đổi.

Chạy:
  .venv\\Scripts\\python.exe scripts/migrate_start_priority_per_zone.py --dry-run
  .venv\\Scripts\\python.exe scripts/migrate_start_priority_per_zone.py
  .venv\\Scripts\\python.exe scripts/migrate_start_priority_per_zone.py --ensure-index
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from pymongo import ASCENDING, MongoClient

MONGO_URI = "mongodb://127.0.0.1:27018"
DB_NAME = "db_kortek"


def _digits_key(node_id: str) -> Tuple[int, str]:
    digits = "".join(ch for ch in node_id if ch.isdigit())
    n = int(digits) if digits else 10**12
    return (n, node_id)


def migrate(db, dry_run: bool) -> int:
    nodes = db["nodes"]
    by_zone: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for doc in nodes.find({"node_type": "start"}):
        z = str(doc.get("zone_id") or "").strip().upper() or "_NO_ZONE_"
        by_zone[z].append(doc)

    updated = 0
    for zone, rows in sorted(by_zone.items()):
        rows_sorted = sorted(rows, key=lambda d: _digits_key(str(d.get("node_id") or "")))
        print(f"\nzone={zone} starts={len(rows_sorted)}")
        for i, doc in enumerate(rows_sorted, start=1):
            nid = doc.get("node_id")
            old = doc.get("priority")
            if old == i:
                print(f"  keep {nid}: priority={i}")
                continue
            print(f"  {nid}: {old} -> {i}")
            updated += 1
            if not dry_run:
                nodes.update_one({"node_id": nid}, {"$set": {"priority": i}})
    return updated


def ensure_index(db) -> None:
    """Unique (zone_id, priority) cho start — partial filter."""
    nodes = db["nodes"]
    name = "uniq_start_zone_priority"
    nodes.create_index(
        [("zone_id", ASCENDING), ("priority", ASCENDING)],
        name=name,
        unique=True,
        partialFilterExpression={"node_type": "start"},
    )
    print(f"index OK: {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--ensure-index",
        action="store_true",
        help="Tạo unique index sau khi data sạch",
    )
    parser.add_argument("--uri", default=MONGO_URI)
    parser.add_argument("--db", default=DB_NAME)
    args = parser.parse_args()

    client = MongoClient(args.uri)
    db = client[args.db]
    n = migrate(db, dry_run=args.dry_run)
    print(f"\n{'would update' if args.dry_run else 'updated'}: {n}")
    if args.ensure_index and not args.dry_run:
        ensure_index(db)
    client.close()


if __name__ == "__main__":
    main()
