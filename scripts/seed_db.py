"""
Script insert 100 mock cameras vào MongoDB cho Kortek
Chạy 1 lần để setup mock data cho stress test
"""
from pymongo import MongoClient
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────
MONGO_URI    = "mongodb://127.0.0.1:27018"
DB_NAME      = "db_kortek"
COLLECTION   = "cameras"
N_CAMERAS    = 20
RTSP_HOST    = "127.0.0.1"
RTSP_PORT    = 8554
ZONE_ID      = "AE5"   # đổi nếu cần
# ────────────────────────────────────────────────────────

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
    # ROI mẫu — giữ nguyên structure từ schema thật
    sample_rois = {
        "start_10000060": {
            "roi": [80, 120, 140, 90],
            "start": True,
            "end": False
        },
        "start_10000059": {
            "roi": [240, 120, 140, 90],
            "start": True,
            "end": False
        },
        "end_10000760": {
            "roi": [80, 280, 140, 90],
            "start": False,
            "end": True
        },
        "end_10000761": {
            "roi": [240, 280, 140, 90],
            "start": False,
            "end": True
        }
    }

    docs = []
    for i in range(1, n + 1):
        doc = {
            "cameraId":   i,
            "name":       f"MOCK-CAM-{i:03d} — stress test",
            "url":        f"rtsp://{RTSP_HOST}:{RTSP_PORT}/cam_{i}",
            "zone_id":    ZONE_ID,
            "enabled":    True,
            "rois":       sample_rois,
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
    print(f"\n✅ Done! Chạy pipeline với {N_CAMERAS} cameras.")
    print(f"   Nhớ đảm bảo FFmpeg đang push lên:")
    print(f"   ffmpeg -re -stream_loop -1 -i input.mp4 -c copy -f rtsp rtsp://{RTSP_HOST}:{RTSP_PORT}/raw_stream")


if __name__ == "__main__":
    main()