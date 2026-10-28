# scripts/mongo_import_all.py
"""Import thư mục JSON (từ mongo_export_all.py) vào DB hiện tại (dev)."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from bson import json_util
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import settings

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("indir", help="Thư mục chứa *.json từ export")
    p.add_argument("--uri", default=settings.MONGODB_URL)
    p.add_argument("--db", default=settings.MONGODB_DB)
    p.add_argument("--drop", action="store_true", help="Xóa collection trước khi insert")
    args = p.parse_args()

    indir = Path(args.indir)
    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    db = client[args.db]

    files = sorted(indir.glob("*.json"))
    files = [f for f in files if f.name != "_meta.json"]
    print(f"Import {len(files)} files -> {args.db}")

    for f in files:
        name = f.stem
        docs = json_util.loads(f.read_text(encoding="utf-8"))
        if not isinstance(docs, list):
            raise SystemExit(f"{f}: expected JSON array")
        col = db[name]
        if args.drop:
            col.drop()
        if docs:
            col.insert_many(docs)
        print(f"  {name}: {len(docs)} docs")
    print("OK")

if __name__ == "__main__":
    main()