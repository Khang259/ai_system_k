from infrastructure.vision.preview_store import PreviewStore


def test_preview_store_watch_and_get():
    store = PreviewStore()
    assert store.is_watched(1) is False
    store.watch(1, ttl_sec=5)
    assert store.is_watched(1) is True
    store.put(1, raw=b"raw", detect=b"det", meta={"ts": 1.0, "dets": []})
    assert store.get_wait(1, detect=False, timeout=0.1) == b"raw"
    assert store.get_wait(1, detect=True, timeout=0.1) == b"det"
    assert store.get_wait_meta(1, timeout=0.1)["ts"] == 1.0


def test_preview_store_timeout_empty():
    store = PreviewStore()
    store.watch(2, ttl_sec=1)
    assert store.get_wait(2, detect=False, timeout=0.05) is None
