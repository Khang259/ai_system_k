"""
Báo cáo start nodes thiếu col_id — ops gán thủ công (không auto-map).

    uv run python scripts/migrate_report_col_id.py
    uv run python scripts/migrate_report_col_id.py --fix
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Report start nodes missing col_id")
    parser.add_argument("--fix", action="store_true", help="exit 1 nếu còn thiếu")
    args = parser.parse_args()

    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[settings.MONGODB_DB]
    missing = list(
        db["nodes"].find(
            {
                "node_type": "start",
                "$or": [
                    {"col_id": {"$exists": False}},
                    {"col_id": None},
                    {"col_id": ""},
                ],
            },
            {"node_id": 1, "zone_id": 1, "priority": 1},
        )
    )
    print(f"starts missing col_id: {len(missing)}")
    for doc in missing:
        print(
            f"  {doc.get('node_id')}  zone={doc.get('zone_id')}  "
            f"priority={doc.get('priority')}"
        )
        print(f"    → PATCH /api/v1/nodes/update_node  colId=...")

    if args.fix and missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
