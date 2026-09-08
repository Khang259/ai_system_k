"""
MediaMTX subprocess + watchdog — optional, không fail app nếu thiếu binary.

Watchdog probe HTTP API định kỳ (bắt được cả instance chạy ngoài app).
Chết mà app là chủ tiến trình → restart có backoff. Chết mà instance ngoài
→ chỉ log error, không tự bật bản của mình lên (tránh tranh port).
"""
from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from utils.setup_log import setup_logger

logger = setup_logger("mediamtx_runner", "logs/webrtc/log")

_ROOT = Path(__file__).resolve().parents[2]

_BACKOFF_START_SEC = 1.0
_BACKOFF_CAP_SEC = 30.0


def _resolve_bin(bin_path: str) -> Optional[str]:
    names = []
    if (bin_path or "").strip():
        names.append(bin_path.strip())
    names.extend(
        [
            str(_ROOT / "bin" / "mediamtx.exe"),
            str(_ROOT / "bin" / "mediamtx"),
            "mediamtx.exe",
            "mediamtx",
        ]
    )
    for name in names:
        path = Path(name)
        if path.is_file():
            return str(path)
        found = shutil.which(name)
        if found:
            return found
    return None


class MediaMtxRunner:
    """
    Quản lý vòng đời MediaMTX. start()/stop() giống PairManager.

    self._proc None = không phải chủ tiến trình (instance chạy ngoài,
    hoặc chưa bật được) → watchdog không restart, chỉ báo động.
    """

    def __init__(
        self,
        bin_path: str,
        yml_path: str,
        api_url: str = "",
        watchdog_sec: float = 10.0,
        max_restarts: int = 5,
    ):
        self.bin_path = bin_path
        self.yml_path = yml_path
        self.api_url = (api_url or "").rstrip("/")
        self.watchdog_sec = float(watchdog_sec)
        self.max_restarts = int(max_restarts)

        self._proc: Optional[subprocess.Popen] = None
        self._external = False       # MediaMTX đã chạy sẵn ngoài app
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._restarts = 0
        self._gave_up = False

    # ── probe ────────────────────────────────────────────────
    def _probe(self) -> bool:
        """Hỏi API còn sống không. Không có api_url → fallback poll tiến trình."""
        if not self.api_url:
            return self._proc is not None and self._proc.poll() is None
        try:
            r = httpx.get(f"{self.api_url}/v3/config/global/get", timeout=0.8)
            return r.status_code < 500
        except Exception:
            return False

    # ── spawn ────────────────────────────────────────────────
    def _spawn(self) -> bool:
        found = _resolve_bin(self.bin_path)
        if found is None:
            logger.warning(
                "MediaMTX binary not found. Tải Windows amd64, đặt bin/mediamtx.exe "
                "hoặc MEDIAMTX_BIN, hoặc chạy: mediamtx config/mediamtx.yml"
            )
            return False

        yml = Path(self.yml_path)
        if not yml.is_absolute():
            yml = _ROOT / yml
        if not yml.is_file():
            logger.warning(f"MediaMTX yml missing: {yml}")
            return False

        try:
            self._proc = subprocess.Popen(
                [found, str(yml)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(f"MediaMTX started pid={self._proc.pid}")
            return True
        except Exception as e:
            logger.warning(f"MediaMTX start failed: {e}")
            self._proc = None
            return False

    # ── lifecycle ────────────────────────────────────────────
    def start(self) -> None:
        if self._probe():
            self._external = True
            logger.info("MediaMTX already running (external instance)")
        else:
            self._spawn()

        if self.watchdog_sec > 0:
            self._stop_flag.clear()
            self._thread = threading.Thread(
                target=self._watchdog_loop, daemon=True, name="MediaMtxWatchdog"
            )
            self._thread.start()
            logger.info(f"MediaMTX watchdog started (probe mỗi {self.watchdog_sec}s)")

    def stop(self) -> None:
        # Hạ cờ TRƯỚC khi kill, nếu không watchdog hồi sinh tiến trình lúc shutdown
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None
        logger.info("MediaMTX stopped")

    # ── watchdog ─────────────────────────────────────────────
    def _watchdog_loop(self) -> None:
        backoff = _BACKOFF_START_SEC

        while not self._stop_flag.wait(self.watchdog_sec):
            if self._probe():
                # Sống lại sau sự cố → reset ngưỡng
                if self._restarts or self._gave_up:
                    logger.info("MediaMTX healthy again — reset restart counter")
                self._restarts = 0
                self._gave_up = False
                backoff = _BACKOFF_START_SEC
                continue

            if self._gave_up:
                continue

            if self._proc is None:
                logger.error(
                    "MediaMTX không phản hồi và app không phải chủ tiến trình "
                    "— WebRTC đang chết, cần khởi động lại thủ công"
                )
                continue

            self._restarts += 1
            if self._restarts > self.max_restarts:
                self._gave_up = True
                logger.error(
                    f"MediaMTX chết {self._restarts - 1} lần liên tiếp — bỏ restart. "
                    "Kiểm tra config/port."
                )
                continue

            logger.warning(
                f"MediaMTX chết — restart lần {self._restarts}/{self.max_restarts} "
                f"sau {backoff:.0f}s"
            )
            # wait() thay vì sleep() để stop() thoát được ngay
            if self._stop_flag.wait(backoff):
                return
            self._spawn()
            backoff = min(backoff * 2, _BACKOFF_CAP_SEC)

    # ── status cho /health ───────────────────────────────────
    def status(self) -> Dict[str, Any]:
        alive = self._probe()
        return {
            "alive": alive,
            "owned": self._proc is not None,
            "external": self._external,
            "restarts": self._restarts,
            "gave_up": self._gave_up,
            "watchdog": self.watchdog_sec > 0,
        }
