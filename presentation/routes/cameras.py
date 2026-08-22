"""Camera routes — presentation maps use case results to HTTP."""
from typing import Any, Dict, Union

from fastapi import APIRouter, Body, Path, Request, Response
from fastapi.responses import JSONResponse

from application.cameras.webrtc_ice import ice_servers_for_browser
from application.container import container
from application.result import UseCaseResult
from presentation.http import to_http, to_http_or_data, to_http_status

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


@router.post("/start-all")
async def start_all_cameras():
    return to_http_status(await container.start_all_cameras.execute())


@router.post("/stop-all")
async def stop_all_cameras() -> Dict[str, Any]:
    return to_http(container.stop_all_cameras.execute())


@router.post("/{zone}/start-all")
async def start_zone_cameras(zone: str) -> Dict[str, Any]:
    return to_http(container.start_zone_cameras.execute(zone))


@router.post("/{zone}/stop-all")
async def stop_zone_cameras(zone: str) -> Dict[str, Any]:
    return to_http(container.stop_zone_cameras.execute(zone))


@router.get("/status")
async def get_camera_status() -> Dict[str, Any]:
    return to_http_or_data(container.get_camera_status.execute())


@router.get("/config")
async def get_all_configs() -> Dict[str, Any]:
    return to_http(await container.list_camera_configs.execute())


@router.get("/config/area/{area}")
async def get_configs_by_area(area: str) -> Dict[str, Any]:
    return to_http(await container.list_camera_configs_by_area.execute(area))


@router.post("/config")
async def create_config(doc: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return to_http(await container.create_camera_config.execute(doc))


@router.put("/config/{camera_id}")
async def update_config(
    camera_id: int = Path(...),
    data: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    return to_http(await container.update_camera_config.execute(camera_id, data))


@router.delete("/config/{camera_id}")
async def delete_config(camera_id: int = Path(...)) -> Dict[str, Any]:
    return to_http(await container.delete_camera_config.execute(camera_id))


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
    responses={
        200: {"content": {"image/jpeg": {}}},
        404: {"description": "Camera not found"},
        409: {"description": "Camera not streaming"},
        503: {"description": "No overlay frame yet"},
    },
)
async def preview_detect(camera_id: int = Path(...)):
    """JPEG đã vẽ ROI + bbox + cls/conf. Swagger Try it out hiện ảnh."""
    return _jpeg_or_error(container.get_camera_preview.execute(camera_id, detect=True))


@router.get(
    "/{camera_id}/preview",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}}},
        404: {"description": "Camera not found"},
        409: {"description": "Camera not streaming"},
        503: {"description": "No frame yet"},
    },
)
async def preview_raw(camera_id: int = Path(...)):
    """JPEG frame infer (640×480 stretch). Chưa passthrough RTSP gốc."""
    return _jpeg_or_error(container.get_camera_preview.execute(camera_id, detect=False))


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
    """DELETE /cameras/{camera_id}/webrtc/sessions/{session_id}"""
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
