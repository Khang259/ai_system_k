from application.cameras.webrtc_sessions import WebrtcSessionRegistry
from application.result import UseCaseResult

_MODES = frozenset({"preview", "detect"})


class OfferWebrtc:
    """WHEP POST. preview|detect + MediaMTX → SDP 201. Detect overlay = GET /preview/meta."""

    def __init__(self, registry: WebrtcSessionRegistry, cameras=None, gateway=None) -> None:
        self._registry = registry
        self._cameras = cameras
        self._gateway = gateway

    def execute(self, camera_id: int, mode: str, sdp_offer: str) -> UseCaseResult:
        if mode not in _MODES:
            return UseCaseResult.fail("mode must be preview or detect", http_status=400)
        if not (sdp_offer or "").strip():
            return UseCaseResult.fail("SDP offer required", http_status=400)

        cam = int(camera_id)
        use_media = self._gateway is not None and self._gateway.is_ready()
        if use_media:
            rtsp = self._cameras.get_rtsp_url(cam) if self._cameras else None
            if not rtsp:
                return UseCaseResult.fail("Camera not found", http_status=404)

        sid = self._registry.create(cam, mode)
        if sid is None:
            return UseCaseResult.fail(
                "Max 4 WebRTC sessions (grid 2x2)",
                http_status=409,
            )

        if use_media:
            try:
                answer, remote = self._gateway.whep_offer(cam, rtsp, sdp_offer)
            except Exception as e:
                self._registry.delete(sid, cam)
                return UseCaseResult.fail(str(e) or "MediaMTX WHEP failed", http_status=503)
            self._registry.set_remote(sid, remote)
            return UseCaseResult.ok(
                sdp=answer,
                session_id=sid,
                camera_id=cam,
                mode=mode,
            )

        return UseCaseResult.fail(
            "WebRTC not ready",
            http_status=503,
            session_id=sid,
            camera_id=cam,
            mode=mode,
        )


class DeleteWebrtcSession:
    def __init__(self, registry: WebrtcSessionRegistry, gateway=None) -> None:
        self._registry = registry
        self._gateway = gateway

    def execute(self, camera_id: int, session_id: str) -> UseCaseResult:
        info = self._registry.pop(session_id, int(camera_id))
        if info is None:
            return UseCaseResult.fail("Session not found", http_status=404)
        remote = info.get("remote")
        if remote and self._gateway is not None:
            try:
                self._gateway.hangup(remote)
            except Exception:
                pass
        return UseCaseResult.ok(session_id=session_id, camera_id=int(camera_id))


class GetWebrtcGrid:
    def __init__(self, registry: WebrtcSessionRegistry) -> None:
        self._registry = registry

    def execute(self) -> UseCaseResult:
        return UseCaseResult.ok(
            count=self._registry.count(),
            max=self._registry.max_sessions,
        )
