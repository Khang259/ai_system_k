"""RAM JPEG preview — chỉ encode cam đang được GET (watch TTL)."""
import threading
import time


class PreviewStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._raw = {}
        self._detect = {}
        self._meta = {}
        self._watch_until = {}

    def watch(self, camera_id: int, ttl_sec: float) -> None:
        with self._cv:
            self._watch_until[int(camera_id)] = time.monotonic() + ttl_sec
            self._cv.notify_all()

    def is_watched(self, camera_id: int) -> bool:
        with self._lock:
            deadline = self._watch_until.get(int(camera_id), 0.0)
            return time.monotonic() < deadline

    def put(self, camera_id: int, raw=None, detect=None, meta=None) -> None:
        cam = int(camera_id)
        with self._cv:
            if raw is not None:
                self._raw[cam] = raw
            if detect is not None:
                self._detect[cam] = detect
            if meta is not None:
                self._meta[cam] = meta
            self._cv.notify_all()

    def get_wait(self, camera_id: int, detect: bool, timeout: float):
        cam = int(camera_id)
        deadline = time.monotonic() + timeout
        with self._cv:
            bucket = self._detect if detect else self._raw
            while bucket.get(cam) is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cv.wait(timeout=remaining)
            return bucket.get(cam)

    def get_wait_meta(self, camera_id: int, timeout: float):
        cam = int(camera_id)
        deadline = time.monotonic() + timeout
        with self._cv:
            while self._meta.get(cam) is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cv.wait(timeout=remaining)
            return self._meta.get(cam)
