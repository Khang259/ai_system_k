"""Optional MediaMTX subprocess — không fail app nếu thiếu binary."""
import shutil
import subprocess
from pathlib import Path

import httpx

from utils.setup_log import setup_logger

logger = setup_logger("mediamtx_runner", "logs/webrtc/log")

_ROOT = Path(__file__).resolve().parents[2]
_proc = None


def _resolve_bin(bin_path: str):
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


def start_mediamtx(bin_path: str, yml_path: str, api_url: str = ""):
    global _proc
    if api_url:
        try:
            r = httpx.get(f"{api_url.rstrip('/')}/v3/config/global/get", timeout=0.8)
            if r.status_code < 500:
                logger.info("MediaMTX already running")
                return None
        except Exception:
            pass

    found = _resolve_bin(bin_path)
    yml = Path(yml_path)
    if not yml.is_absolute():
        yml = _ROOT / yml
    if found is None:
        logger.warning(
            "MediaMTX binary not found. Tải Windows amd64, đặt bin/mediamtx.exe "
            "hoặc MEDIAMTX_BIN, hoặc chạy: mediamtx config/mediamtx.yml"
        )
        return None
    if not yml.is_file():
        logger.warning(f"MediaMTX yml missing: {yml}")
        return None
    try:
        _proc = subprocess.Popen(
            [found, str(yml)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"MediaMTX started pid={_proc.pid}")
        return _proc
    except Exception as e:
        logger.warning(f"MediaMTX start failed: {e}")
        return None


def stop_mediamtx():
    global _proc
    if _proc is None:
        return
    try:
        _proc.terminate()
        _proc.wait(timeout=3)
    except Exception:
        try:
            _proc.kill()
        except Exception:
            pass
    _proc = None
