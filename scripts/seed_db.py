"""
Nạp seed Mongo từ data/seed.json.

  python scripts/seed_db.py --replace
  python scripts/seed_db.py --append

--replace: xóa 4 collection rồi insert lại (mặc định, an toàn khi chỉnh seed).
--append:  chỉ insert, không xóa (có thể trùng cameraId / node_id).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "seed.json"
COLLECTIONS = ("zones", "cameras", "nodes", "pairs")

sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402
from infrastructure.persistence.db import connect, disconnect, get_db  # noqa: E402


def _load_seed() -> dict:
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    missing = [name for name in COLLECTIONS if name not in raw]
    if missing:
        raise SystemExit(f"seed.json thiếu collection: {missing}")
    return raw


def _stamp(docs: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []
    for doc in docs:
        item = dict(doc)
        item.setdefault("created_at", now)
        out.append(item)
    return out


async def seed(replace: bool) -> None:
    data = _load_seed()
    await connect(settings.MONGODB_URL, settings.MONGODB_DB)
    db = get_db()

    for name in COLLECTIONS:
        col = db[name]
        docs = _stamp(data[name])
        if replace:
            deleted = await col.delete_many({})
            print(f"[{name}] deleted {deleted.deleted_count}")
        if not docs:
            print(f"[{name}] skip (empty)")
            continue
        result = await col.insert_many(docs)
        print(f"[{name}] inserted {len(result.inserted_ids)}")

    await disconnect()
    print(f"Done → {settings.MONGODB_DB} @ {settings.MONGODB_URL}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Mongo collections from data/seed.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--replace", dest="replace", action="store_true", help="Xóa rồi insert (mặc định)")
    mode.add_argument("--append", dest="replace", action="store_false", help="Chỉ insert, không xóa")
    parser.set_defaults(replace=True)
    args = parser.parse_args()
    asyncio.run(seed(replace=args.replace))


if __name__ == "__main__":
    main()
