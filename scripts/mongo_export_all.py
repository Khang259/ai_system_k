# scripts/mongo_export_all.py
"""Export toàn bộ collection → thư mục JSON (prod). Import bằng mongo_import_all.py."""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime
from pathlib import Path
from bson import json_util
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import settings

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--uri", default=settings.MONGODB_URL)
    p.add_argument("--db", default=settings.MONGODB_DB)
    p.add_argument("--out", default=None, help="Thư mục output")
    args = p.parse_args()

    out = Path(args.out or f"data/mongo_export_{datetime.now():%Y%m%d_%H%M%S}")
    out.mkdir(parents=True, exist_ok=True)

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    db = client[args.db]
    names = sorted(db.list_collection_names())
    print(f"DB={args.db}  collections={len(names)}  -> {out}")

    meta = {"db": args.db, "collections": {}}
    for name in names:
        if name.startswith("system."):
            continue
        docs = list(db[name].find({}))
        path = out / f"{name}.json"
        path.write_text(json_util.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
        meta["collections"][name] = len(docs)
        print(f"  {name}: {len(docs)} docs")

    (out / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("OK")

if __name__ == "__main__":
    main()