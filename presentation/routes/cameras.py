"""Camera routes ngoài `/api/v1` — WebRTC + preview (contract FE GIỮ_FE / GIỮ_ops)."""
from typing import Any, Dict, Union

from fastapi import APIRouter, Path, Request, Response
from fastapi.responses import JSONResponse

from application.cameras.webrtc_ice import ice_servers_for_browser
from application.container import container
from application.result import UseCaseResult
from presentation.http import to_http_or_data

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _json_or_error(result: UseCaseResult) -> Union[Dict[str, Any], JSONResponse]:
    if result.success:
        return result.data
    status = int(result.data.get("http_status") or 503)
    return JSONResponse(status_code=status, content=result.to_http())


def _jpeg_or_error(result: UseCaseResult) -> Union[Response, JSONResponse]:
    if result.success:
        return Response(content=result.data["jpeg"], media_type="image/jpeg")
    status = int(result.data.get("http_status") or 503)
    return JSONResponse(status_code=status, content=result.to_http())


@router.get("/webrtc/status")
async def webrtc_status() -> Dict[str, Any]:
    """Slot grid 2×2: count / max."""
    return to_http_or_data(container.get_webrtc_grid.execute())


@router.get("/webrtc/ice")
async def webrtc_ice() -> Dict[str, Any]:
    """ICE cho RTCPeerConnection. Rỗng = LAN, không STUN/TURN."""
    return {"iceServers": ice_servers_for_browser()}


@router.get(
    "/{camera_id}/preview/meta",
    summary="JSON ROI + dets + ts (F5 canvas, không gian 640×480)",
    responses={
        200: {"description": "rois + dets[{cls,conf,xyxy}] + ts"},
        404: {"description": "Camera not found"},
        409: {"description": "Camera not streaming"},
        503: {"description": "No meta yet"},
    },
)
async def preview_meta(camera_id: int = Path(...)):
    return _json_or_error(container.get_camera_preview_meta.execute(camera_id))


@router.get(
    "/{camera_id}/preview/detect",
    response_class=Response,
    summary="JPEG đã vẽ ROI + bbox — demo/ops (FE production không gọi)",
    responses={
        200: {"content": {"image/jpeg": {}}},
        404: {"description": "Camera not found"},
        409: {"description": "Camera not streaming"},
        503: {"description": "No overlay frame yet"},
    },
)
async def preview_detect(camera_id: int = Path(...)):
    return _jpeg_or_error(container.get_camera_preview.execute(camera_id, detect=True))


@router.post(
    "/{camera_id}/webrtc/preview/whep",
    summary="WHEP preview (SDP offer → answer khi MediaMTX sẵn sàng)",
    responses={
        201: {"content": {"application/sdp": {}}},
        404: {"description": "Camera / RTSP not found"},
        409: {"description": "Max 4 sessions"},
        503: {"description": "MediaMTX chưa sẵn sàng"},
    },
)
async def whep_preview(camera_id: int, request: Request):
    offer = (await request.body()).decode("utf-8", errors="replace")
    result = container.offer_webrtc.execute(camera_id, "preview", offer)
    return _whep_or_error(result)


@router.post(
    "/{camera_id}/webrtc/detect/whep",
    summary="WHEP detect — video giống preview; overlay = GET /preview/meta",
    responses={
        201: {"content": {"application/sdp": {}}},
        409: {"description": "Max 4 sessions"},
        503: {"description": "MediaMTX chưa sẵn sàng"},
    },
)
async def whep_detect(camera_id: int, request: Request):
    offer = (await request.body()).decode("utf-8", errors="replace")
    result = container.offer_webrtc.execute(camera_id, "detect", offer)
    return _whep_or_error(result)


@router.delete(
    "/{camera_id}/webrtc/sessions/{session_id}",
    summary="Hangup WebRTC — giải phóng slot (+ MediaMTX subscriber)",
    responses={
        200: {"description": "Session closed"},
        404: {"description": "Session not found"},
    },
)
async def whep_hangup(camera_id: int, session_id: str):
    result = container.delete_webrtc_session.execute(camera_id, session_id)
    if result.success:
        return result.to_http()
    status = int(result.data.get("http_status") or 404)
    return JSONResponse(status_code=status, content=result.to_http())


def _whep_or_error(result: UseCaseResult) -> Union[Response, JSONResponse]:
    if result.success:
        sid = result.data["session_id"]
        cam = result.data["camera_id"]
        return Response(
            content=result.data["sdp"],
            media_type="application/sdp",
            status_code=201,
            headers={"Location": f"/cameras/{cam}/webrtc/sessions/{sid}"},
        )
    status = int(result.data.get("http_status") or 503)
    return JSONResponse(status_code=status, content=result.to_http())
