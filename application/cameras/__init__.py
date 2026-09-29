"""Camera use cases — start/stop, preview, WebRTC, scan control."""
from application.cameras.confirm_ready import ConfirmReady
from application.cameras.on_dispatch_success import OnDispatchSuccess
from application.cameras.pause_scan import PauseScan
from application.cameras.preview import GetCameraPreview, GetCameraPreviewMeta
from application.cameras.start_stop import StartAllCameras, StopAllCameras
from application.cameras.webrtc_ice import ice_servers_for_browser, ice_servers_for_mediamtx
from application.cameras.webrtc_sessions import WebrtcSessionRegistry
from application.cameras.webrtc_signaling import (
    DeleteWebrtcSession,
    GetWebrtcGrid,
    OfferWebrtc,
)
from application.cameras.zone import StartZoneCameras, StopZoneCameras

__all__ = [
    "ConfirmReady",
    "DeleteWebrtcSession",
    "GetCameraPreview",
    "GetCameraPreviewMeta",
    "GetWebrtcGrid",
    "OfferWebrtc",
    "OnDispatchSuccess",
    "PauseScan",
    "StartAllCameras",
    "StartZoneCameras",
    "StopAllCameras",
    "StopZoneCameras",
    "WebrtcSessionRegistry",
    "ice_servers_for_browser",
    "ice_servers_for_mediamtx",
]
