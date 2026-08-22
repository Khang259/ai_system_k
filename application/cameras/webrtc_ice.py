"""ICE servers cho browser (urls) và MediaMTX (url). Trống = LAN, không STUN."""
from typing import Dict, List

from config.settings import settings


def ice_servers_for_browser() -> List[Dict]:
    out: List[Dict] = []
    stun = (settings.WEBRTC_STUN_URL or "").strip()
    if stun:
        out.append({"urls": stun})
    turn = (settings.WEBRTC_TURN_URL or "").strip()
    if turn:
        entry: Dict = {"urls": turn}
        user = (settings.WEBRTC_TURN_USER or "").strip()
        if user:
            entry["username"] = user
            entry["credential"] = settings.WEBRTC_TURN_PASS or ""
        out.append(entry)
    return out


def ice_servers_for_mediamtx() -> List[Dict]:
    out: List[Dict] = []
    stun = (settings.WEBRTC_STUN_URL or "").strip()
    if stun:
        out.append({"url": stun})
    turn = (settings.WEBRTC_TURN_URL or "").strip()
    if turn:
        entry: Dict = {"url": turn}
        user = (settings.WEBRTC_TURN_USER or "").strip()
        if user:
            entry["username"] = user
            entry["password"] = settings.WEBRTC_TURN_PASS or ""
        out.append(entry)
    return out
