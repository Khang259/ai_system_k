"""
Seed dữ liệu sandbox: 2 zone × 10 start + 1 end/zone (không pair xuyên zone).

Chỉ ghi vào DB có tên kết thúc `_sandbox` — xoá sạch cameras / nodes / pairs / zones
của DB đó rồi tạo lại, không đụng DB thật.

    # .env: RUNTIME_MODE=sandbox, MONGODB_DB=db_kortek_sandbox
    uv run python scripts/seed_sandbox.py
    uv run python scripts/seed_users.py      # user đăng nhập cho DB sandbox

Node id chỉ dùng số sau `start_` / `end_` vì orderId ICS chỉ giữ phần số.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Cho phép import package của dự án khi chạy trực tiếp file này
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings
from domain.dispatch.priority import start_meta_from_docs, start_sort_key

ZONES = ("SBA", "SBB")
STARTS_PER_ZONE = 10
# Mỗi zone 1 end riêng — không ghép xuyên zone
END_BY_ZONE = {"SBA": "end_9000101", "SBB": "end_9000102"}
ROI = [0.0, 0.0, 100.0, 100.0]
COLLECTIONS = ("cameras", "nodes", "pairs", "zones")


def _roi_doc(is_start: bool) -> dict:
    return {
        "roi": ROI,
        "start": is_start,
        "end": not is_start,
        "ref_width": settings.MODEL_WIDTH,
        "ref_height": settings.MODEL_HEIGHT,
    }


def _node_doc(node_id: str, node_type: str, zone: str, camera_id: int, priority: int) -> dict:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "zone_id": zone,
        "camera_id": camera_id,
        "priority": priority,
        "enabled": True,
        "is_under_maintenance": False,
        "maintenance_reason": "",
        "lock": {"user": False, "system": False, "orderId": None},
    }


def _camera_doc(camera_id: int, zone: str, node_ids: list, is_start: bool) -> dict:
    return {
        "cameraId": camera_id,
        "name": f"SANDBOX-CAM-{camera_id:02d}",
        "url": f"sandbox://cam_{camera_id}",
        "zone_id": zone,
        "enabled": True,
        "rois": {nid: _roi_doc(is_start) for nid in node_ids},
    }


def build_docs() -> dict:
    """Mỗi start một camera + 1 camera end mỗi zone."""
    cameras, nodes, pairs = [], [], []
    camera_id = 0
    for zone_index, zone in enumerate(ZONES):
        end_node = END_BY_ZONE[zone]
        for priority in range(1, STARTS_PER_ZONE + 1):
            camera_id += 1
            node_id = f"start_{9000000 + zone_index * STARTS_PER_ZONE + priority}"
            cameras.append(_camera_doc(camera_id, zone, [node_id], is_start=True))
            nodes.append(_node_doc(node_id, "start", zone, camera_id, priority))
            pairs.append({
                "start_point": node_id,
                "end_point": end_node,
                "pair_type": "normal",
                "enabled": True,
                "auto_dispatch": True,
            })

        camera_id += 1
        cameras.append(_camera_doc(camera_id, zone, [end_node], is_start=False))
        nodes.append(_node_doc(end_node, "end", zone, camera_id, 1))

    zones = [{"zone_id": z, "name": f"Sandbox {z}", "enabled": True} for z in ZONES]
    return {"cameras": cameras, "nodes": nodes, "pairs": pairs, "zones": zones}


def main() -> int:
    db_name = settings.MONGODB_DB
    if not db_name.endswith("_sandbox"):
        print(f"❌ MONGODB_DB='{db_name}' — chỉ seed DB kết thúc bằng '_sandbox'")
        return 1

    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    docs = build_docs()
    for name in COLLECTIONS:
        db[name].delete_many({})
        db[name].insert_many(docs[name])
        print(f"✅ {name}: {len(docs[name])}")
    client.close()

    meta = start_meta_from_docs(docs["nodes"])
    print(f"\n📋 Thứ tự mong đợi theo từng zone (DB {db_name}):")
    for zone in ZONES:
        ordered = sorted(
            (nid for nid, m in meta.items() if m.get("zone_id") == zone),
            key=lambda nid: start_sort_key(nid, meta),
        )
        end = END_BY_ZONE[zone]
        print(f"   {zone} → {end}:")
        for i, nid in enumerate(ordered, 1):
            print(f"      {i:2d}. {nid}  P{meta[nid]['priority']}")
    print("\n   (Hai zone chạy song song — không đối chiếu thứ tự xen kẽ giữa zone)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
