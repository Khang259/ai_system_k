"""MediaMTX WHEP client — RTSP passthrough, không transcode."""
from urllib.parse import urljoin

import httpx

from utils.setup_log import setup_logger

logger = setup_logger("mediamtx_gateway", "logs/webrtc/log")


def path_name(camera_id: int) -> str:
    return f"cam{int(camera_id)}"


class MediaMtxGateway:
    def __init__(self, api_url: str, webrtc_url: str):
        self.api_url = api_url.rstrip("/")
        self.webrtc_url = webrtc_url.rstrip("/")
        self._ok = False

    def is_ready(self) -> bool:
        try:
            r = httpx.get(f"{self.api_url}/v3/config/global/get", timeout=0.8)
            self._ok = r.status_code < 500
        except Exception:
            self._ok = False
        return self._ok

    def _ensure_path(self, camera_id: int, rtsp: str) -> None:
        name = path_name(camera_id)
        body = {
            "source": rtsp,
            "sourceOnDemand": True,
            "rtspTransport": "tcp",
        }
        add = httpx.post(
            f"{self.api_url}/v3/config/paths/add/{name}",
            json=body,
            timeout=5.0,
        )
        if add.status_code in (200, 201):
            return
        patch = httpx.patch(
            f"{self.api_url}/v3/config/paths/patch/{name}",
            json=body,
            timeout=5.0,
        )
        if patch.status_code >= 400:
            logger.warning(f"MediaMTX path {name}: add={add.status_code} patch={patch.status_code}")

    def whep_offer(self, camera_id: int, rtsp: str, sdp_offer: str):
        self._ensure_path(camera_id, rtsp)
        name = path_name(camera_id)
        url = f"{self.webrtc_url}/{name}/whep"
        r = httpx.post(
            url,
            content=sdp_offer.encode("utf-8"),
            headers={"Content-Type": "application/sdp"},
            timeout=15.0,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"MediaMTX WHEP {r.status_code}: {r.text[:200]}")
        loc = r.headers.get("Location") or ""
        if loc and not loc.startswith("http"):
            loc = urljoin(self.webrtc_url + "/", loc.lstrip("/"))
        if not loc:
            loc = url
        return r.text, loc

    def hangup(self, remote: str) -> None:
        if not remote:
            return
        try:
            httpx.delete(remote, timeout=5.0)
        except Exception as e:
            logger.warning(f"MediaMTX hangup failed: {e}")

    def apply_ice_servers(self, servers) -> None:
        if not servers:
            return
        try:
            r = httpx.patch(
                f"{self.api_url}/v3/config/global/patch",
                json={"webrtcICEServers2": servers},
                timeout=3.0,
            )
            if r.status_code >= 400:
                logger.warning(f"MediaMTX ICE patch {r.status_code}")
        except Exception as e:
            logger.warning(f"MediaMTX ICE patch failed: {e}")


class NullWebrtcGateway:
    def is_ready(self) -> bool:
        return False

    def whep_offer(self, camera_id, rtsp, sdp_offer):
        raise RuntimeError("WebRTC not ready")

    def hangup(self, remote: str) -> None:
        return None

    def apply_ice_servers(self, servers) -> None:
        return None
