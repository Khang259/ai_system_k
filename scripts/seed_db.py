"""
Script insert 100 mock cameras vào MongoDB cho Kortek
Chạy 1 lần để setup mock data cho stress test
"""
from pymongo import MongoClient
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────
MONGO_URI    = "mongodb://127.0.0.1:27017"
DB_NAME      = "db_kortek"
COLLECTION   = "cameras"
RTSP_USER    = "admin"
RTSP_PASS    = "Kortek2026#"
RTSP_PORT    = 554
RTSP_PATH    = "/Streaming/Channels/102"
ZONE_ID      = "AE5"   # đổi nếu cần

CAMERA_IPS = [
    "192.168.50.111",
    "192.168.50.112",
    "192.168.50.113",
    "192.168.50.114",
    "192.168.50.115",
    "192.168.50.116",
    "192.168.50.117",
    "192.168.50.118",
    "192.168.50.119",
    "192.168.50.120",
    "192.168.50.121",
    "192.168.50.122",
    "192.168.50.123",
    "192.168.50.124",
    "192.168.50.125",
    "192.168.50.126",
]
N_CAMERAS = len(CAMERA_IPS)
# ────────────────────────────────────────────────────────

def make_rtsp_url(ip: str) -> str:
    """rtsp://user:pass@ip:port/path — Hikvision sub-stream (channel 102)."""
    return f"rtsp://{RTSP_USER}:{RTSP_PASS}@{ip}:{RTSP_PORT}{RTSP_PATH}"


def generate_camera_docs(n: int) -> list[dict]:
    """
    Generate N camera documents theo đúng schema Kortek:
    - cameraId: int
    - name: str
    - url: rtsp://...
    - zone_id: str
    - enabled: bool
    - rois: dict (giữ nguyên ROI mẫu từ schema thật)
    - created_at: datetime
    """
    # ROI chỉ gắn cam 1 (start) / cam 2 (end) — tránh clone ROI → nhiều cam ghi đè node
    rois_cam1 = {
        "start_10000060": {
            "roi": [80, 120, 140, 90],
            "start": True,
            "end": False,
        },
        "start_10000059": {
            "roi": [240, 120, 140, 90],
            "start": True,
            "end": False,
        },
    }
    rois_cam2 = {
        "end_10000061": {
            "roi": [80, 280, 140, 90],
            "start": False,
            "end": True,
        },
        "end_10000062": {
            "roi": [240, 280, 140, 90],
            "start": False,
            "end": True,
        },
    }

    docs = []
    for i in range(1, n + 1):
        if i == 1:
            rois = rois_cam1
        elif i == 2:
            rois = rois_cam2
        else:
            rois = {}
        ip = CAMERA_IPS[i - 1]
        doc = {
            "cameraId":   i,
            "name":       f"MOCK-CAM-{i:03d} — stress test",
            "url":        make_rtsp_url(ip),
            "zone_id":    ZONE_ID,
            "enabled":    True,
            "rois":       rois,
            "created_at": datetime.now(timezone.utc),
        }
        docs.append(doc)
    return docs


def main():
    client = MongoClient(MONGO_URI)
    db     = client[DB_NAME]
    col    = db[COLLECTION]

    # Xóa mock cameras cũ nếu có
    deleted = col.delete_many({"name": {"$regex": "^MOCK-CAM-"}})
    print(f"🗑️  Deleted {deleted.deleted_count} old mock cameras")

    # Insert N cameras mới
    docs   = generate_camera_docs(N_CAMERAS)
    result = col.insert_many(docs)
    print(f"✅ Inserted {len(result.inserted_ids)} mock cameras")

    # Verify
    total = col.count_documents({})
    mock  = col.count_documents({"name": {"$regex": "^MOCK-CAM-"}})
    real  = total - mock
    print(f"\n📊 DB summary:")
    print(f"   Real cameras:  {real}")
    print(f"   Mock cameras:  {mock}")
    print(f"   Total:         {total}")

    # Print sample URLs
    print(f"\n📹 Sample RTSP URLs:")
    for cam in col.find(
        {"name": {"$regex": "^MOCK-CAM-"}},
        {"url": 1, "name": 1}
    ).limit(3):
        print(f"   [{cam['name']}] {cam['url']}")
    print(f"   ...")
    last = col.find_one({"name": f"MOCK-CAM-{N_CAMERAS:03d} — stress test"})
    if last:
        print(f"   [{last['name']}] {last['url']}")

    client.close()
    print(f"\n✅ Done! Chạy pipeline với {N_CAMERAS} cameras (IP thật).")


if __name__ == "__main__":
    main()