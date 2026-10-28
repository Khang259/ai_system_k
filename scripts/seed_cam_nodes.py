"""
Xoá camera/node cũ (topo trước) rồi seed lại theo mapping:

  Cam8  (.118): start 57,59,56,58,69,93
  Cam11 (.121): start 73,96,76,100,81,103
  Cam13 (.123): start 84,106,87,109,90,112
  Cam16 (.126): end 013

ROI placeholder — toạ độ chỉnh sau trên FE.
Upsert: sau khi xoá, insert docs mới (field mặc định giống seed_topo).

    uv run python scripts/seed_cam_nodes.py --dry-run
    uv run python scripts/seed_cam_nodes.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import MongoClient

from config.settings import settings

# CamN → 192.168.50.(110+N) — khớp seed_db CAMERA_IPS
RTSP_USER = "admin"
RTSP_PASS = "Kortek2026#"
RTSP_PORT = 554
RTSP_PATH = "/Streaming/Channels/102"
ZONE_ID = "X"
ROI = [0.0, 0.0, 100.0, 100.0]

# Camera cũ từ seed_topo + cam mới — xoá trước khi seed
DELETE_CAMERA_IDS = (8, 9, 10, 11, 13, 14, 15, 16)

# Node cũ seed_topo (A1–D9 + Line1/Line2) — xoá cùng đợt
OLD_TOPO_NODE_IDS = [
    "start_10000004",
    "start_10000066",
    "start_10000007",
    "start_10000077",
    "start_10000081",
    "start_10000085",
    "start_10000089",
    "start_10000093",
    "start_10000097",
    "start_10000010",
    "start_10000067",
    "start_10000013",
    "start_10000078",
    "start_10000082",
    "start_10000086",
    "start_10000090",
    "start_10000094",
    "start_10000098",
    "start_10000068",
    "start_10000070",
    "start_10000072",
    "start_10000079",
    "start_10000083",
    "start_10000087",
    "start_10000091",
    "start_10000095",
    "start_10000099",
    "start_10000069",
    "start_10000071",
    "start_10000073",
    "start_10000080",
    "start_10000084",
    "start_10000088",
    "start_10000092",
    "start_10000096",
    "start_10000100",
    "end_10000105",
    "end_10000106",
]

# (camera_id, [suffix...]) — suffix → start_10000{suffix} / end_10000{suffix}
STARTS_BY_CAM: dict[int, list[str]] = {
    8: ["57", "59", "56", "58", "69", "93"],
    11: ["73", "96", "76", "100", "81", "103"],
    13: ["84", "106", "87", "109", "90", "112"],
}
END_SUFFIX = "013"  # end_10000013
END_CAMERA_ID = 16
SEED_CAMERA_IDS = (8, 11, 13, 16)


def _code(suffix: str) -> str:
    """'57' → '10000057', '013' → '10000013', '100' → '10000100'."""
    return f"10000{suffix.zfill(3)}" if len(suffix) <= 3 else f"1000{suffix.zfill(4)}"


def _start_id(suffix: str) -> str:
    return f"start_{_code(suffix)}"


def _end_id(suffix: str) -> str:
    return f"end_{_code(suffix)}"


def _rtsp(camera_id: int) -> str:
    ip = f"192.168.50.{110 + camera_id}"
    return f"rtsp://{RTSP_USER}:{RTSP_PASS}@{ip}:{RTSP_PORT}{RTSP_PATH}"


def _roi_doc(is_start: bool) -> dict:
    return {
        "roi": list(ROI),
        "start": is_start,
        "end": not is_start,
        "ref_width": settings.MODEL_WIDTH,
        "ref_height": settings.MODEL_HEIGHT,
    }


def _node_doc(
    node_id: str, node_type: str, camera_id: int, priority: int
) -> dict:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "zone_id": ZONE_ID,
        "camera_id": camera_id,
        "priority": priority,
        "enabled": True,
        "is_under_maintenance": False,
        "maintenance_reason": "",
        "lock": {"user": False, "system": False, "orderId": None},
    }


def build_docs() -> dict:
    nodes: list[dict] = []
    rois_by_cam: dict[int, dict] = {cid: {} for cid in SEED_CAMERA_IDS}
    priority = 0

    for cam_id, suffixes in STARTS_BY_CAM.items():
        for suffix in suffixes:
            priority += 1
            nid = _start_id(suffix)
            nodes.append(_node_doc(nid, "start", cam_id, priority))
            rois_by_cam[cam_id][nid] = _roi_doc(is_start=True)

    end_nid = _end_id(END_SUFFIX)
    nodes.append(_node_doc(end_nid, "end", END_CAMERA_ID, 1))
    rois_by_cam[END_CAMERA_ID][end_nid] = _roi_doc(is_start=False)

    cameras = [
        {
            "cameraId": cid,
            "name": f"Cam{cid}",
            "url": _rtsp(cid),
            "zone_id": ZONE_ID,
            "enabled": True,
            "rois": rois_by_cam[cid],
        }
        for cid in SEED_CAMERA_IDS
    ]
    return {"cameras": cameras, "nodes": nodes}


def node_ids_to_delete(new_nodes: list[dict]) -> list[str]:
    ids = set(OLD_TOPO_NODE_IDS)
    ids.update(n["node_id"] for n in new_nodes)
    return sorted(ids)


def print_plan(docs: dict) -> None:
    print("[PLAN] cameras (sau khi xoá cũ):")
    for c in docs["cameras"]:
        ip = f"192.168.50.{110 + c['cameraId']}"
        print(f"   Cam{c['cameraId']}  {ip}  rois={list(c['rois'].keys())}")
        print(f"      url={c['url']}")
    print(f"\n[PLAN] nodes ({len(docs['nodes'])}):")
    for n in docs["nodes"]:
        print(
            f"   {n['node_id']:20s}  type={n['node_type']:5s}  "
            f"camera_id={n['camera_id']:2d}  priority={n['priority']}"
        )
    print(f"\n[PLAN] xoá cameraId in {list(DELETE_CAMERA_IDS)}")
    print(f"[PLAN] xoá {len(node_ids_to_delete(docs['nodes']))} node_id (cũ + mới)")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Seed cameras + nodes (Cam8/11/13/16)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_name = settings.MONGODB_DB
    if db_name.endswith("_sandbox"):
        print(f"[ERR] MONGODB_DB='{db_name}' — dùng seed_sandbox.py")
        return 1

    docs = build_docs()
    print_plan(docs)

    if args.dry_run:
        print(f"\n(dry-run — chưa ghi DB {db_name})")
        return 0

    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[db_name]

        del_cams = db["cameras"].delete_many(
            {"cameraId": {"$in": list(DELETE_CAMERA_IDS)}}
        )
        del_nodes = db["nodes"].delete_many(
            {"node_id": {"$in": node_ids_to_delete(docs["nodes"])}}
        )
        print(
            f"\n[DEL] cameras={del_cams.deleted_count}, "
            f"nodes={del_nodes.deleted_count}"
        )

        db["cameras"].insert_many(docs["cameras"])
        db["nodes"].insert_many(docs["nodes"])
        print(
            f"[OK] DB {db_name}: inserted cameras={len(docs['cameras'])}, "
            f"nodes={len(docs['nodes'])}"
        )
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
