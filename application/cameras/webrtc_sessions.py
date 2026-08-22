"""In-memory WebRTC signaling sessions — max grid 2×2."""
from __future__ import annotations

import threading
import uuid
from typing import Dict, Optional


class WebrtcSessionRegistry:
    def __init__(self, max_sessions: int = 4):
        self.max_sessions = max(1, int(max_sessions))
        self._lock = threading.Lock()
        self._sessions: Dict[str, dict] = {}

    def create(self, camera_id: int, mode: str) -> Optional[str]:
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                return None
            sid = uuid.uuid4().hex[:12]
            self._sessions[sid] = {
                "session_id": sid,
                "camera_id": int(camera_id),
                "mode": mode,
                "remote": None,
            }
            return sid

    def set_remote(self, session_id: str, remote: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["remote"] = remote

    def pop(self, session_id: str, camera_id: int) -> Optional[dict]:
        with self._lock:
            info = self._sessions.get(session_id)
            if info is None or int(info["camera_id"]) != int(camera_id):
                return None
            del self._sessions[session_id]
            return info

    def delete(self, session_id: str, camera_id: int) -> bool:
        return self.pop(session_id, camera_id) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def drain(self) -> list:
        with self._lock:
            items = list(self._sessions.values())
            self._sessions.clear()
            return items

    def clear(self) -> None:
        self.drain()
