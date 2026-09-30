"""Camera routes — `/api/v1/cameras/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import Response

from application.cameras import ice_servers_for_browser
from application.container import container
from domain.permissions import CAMERA_READ, CAMERA_WRITE
from presentation.deps import require_permission
from presentation.http_v1 import audited_or_error, data_or_error, jpeg_or_error, sdp_or_error
from presentation.openapi_responses import (
    JPEG_SNAPSHOT,
    PREVIEW_META,
    WHEP_CONNECT,
    WHEP_DETECT,
    WHEP_HANGUP,
)
from presentation.schemas import (
    CreateRoiPayload,
    DeleteCameraPayload,
    DeleteRoiPayload,
    SetCameraStatusPayload,
    UpdateCameraPayload,
    UpdateRoiPayload,
)

router = APIRouter()


@router.get(
    "/webrtc/status",
    summary="Slot grid WebRTC 2×2: count / max",
)
async def webrtc_status(
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Dict[str, Any]:
    return data_or_error(container.get_webrtc_grid.execute())


@router.get(
    "/webrtc/ice",
    summary="ICE servers cho RTCPeerConnection",
)
async def webrtc_ice(
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Dict[str, Any]:
    return {"iceServers": ice_servers_for_browser()}


@router.get(
    "/{camera_id}/preview/meta",
    summary="JSON ROI + dets + ts (F5 canvas, không gian 640×480)",
    responses=PREVIEW_META,
)
async def preview_meta(
    camera_id: int = Path(...),
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Dict[str, Any]:
    return data_or_error(
        container.get_camera_preview_meta.execute(camera_id),
        fail_status=503,
    )


@router.post(
    "/{camera_id}/webrtc/preview/whep",
    summary="WHEP preview (SDP offer → answer khi MediaMTX sẵn sàng)",
    responses=WHEP_CONNECT,
)
async def whep_preview(
    camera_id: int,
    request: Request,
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Response:
    offer = (await request.body()).decode("utf-8", errors="replace")
    result = container.offer_webrtc.execute(camera_id, "preview", offer)
    sid = (result.data or {}).get("session_id") or ""
    return sdp_or_error(
        result,
        location=f"/api/v1/cameras/{camera_id}/webrtc/sessions/{sid}",
    )


@router.post(
    "/{camera_id}/webrtc/detect/whep",
    summary="WHEP detect — video giống preview; overlay = GET .../preview/meta",
    responses=WHEP_DETECT,
)
async def whep_detect(
    camera_id: int,
    request: Request,
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Response:
    offer = (await request.body()).decode("utf-8", errors="replace")
    result = container.offer_webrtc.execute(camera_id, "detect", offer)
    sid = (result.data or {}).get("session_id") or ""
    return sdp_or_error(
        result,
        location=f"/api/v1/cameras/{camera_id}/webrtc/sessions/{sid}",
    )


@router.delete(
    "/{camera_id}/webrtc/sessions/{session_id}",
    summary="Hangup WebRTC — giải phóng slot (+ MediaMTX subscriber)",
    responses=WHEP_HANGUP,
)
async def whep_hangup(
    camera_id: int,
    session_id: str,
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Dict[str, Any]:
    return data_or_error(
        container.delete_webrtc_session.execute(camera_id, session_id),
        fail_status=404,
    )


@router.get(
    "/get_cameras",
    summary="Danh sách camera — gộp Mongo config + runtime status",
)
async def get_cameras(
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_cameras_v1.execute())


@router.get(
    "/get_snapshot",
    response_class=Response,
    summary="JPEG frame infer 640×480",
    responses=JPEG_SNAPSHOT,
)
def get_snapshot(
    cameraId: int = Query(..., description="Id camera trong Mongo"),
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Response:
    return jpeg_or_error(container.get_camera_preview.execute(cameraId, detect=False))


@router.get(
    "/get_rois",
    summary="Danh sách ROI — pixel [x,y,w,h] trong 640×480",
)
async def get_rois(
    cameraId: Optional[int] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(CAMERA_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_rois_v1.execute(cameraId))


@router.post(
    "/set_camera_status",
    summary="Bật/tắt camera + cascade enabled trên nodes/pairs (cần inference pause)",
)
async def set_camera_status(
    payload: SetCameraStatusPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.set_camera_status_v1.execute(
        payload.cameraId, payload.enabled
    )
    return await audited_or_error(
        result, request, user, "set_camera_status", payload.model_dump()
    )


@router.patch(
    "/update_camera",
    summary="Sửa name / RTSP / zone / observedNodeIds — cascade xóa node/pair khi gỡ",
)
async def update_camera(
    payload: UpdateCameraPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.update_camera_v1.execute(
        payload.cameraId,
        name=payload.name,
        rtsp_url=payload.rtspUrl,
        zone=payload.zone,
        observed_node_ids=payload.observedNodeIds,
    )
    return await audited_or_error(
        result, request, user, "update_camera", payload.model_dump(exclude_none=True)
    )


@router.post(
    "/delete_camera",
    summary="Xóa camera + cascade nodes + pairs + ROI",
)
async def delete_camera(
    payload: DeleteCameraPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.delete_camera_v1.execute(payload.cameraId)
    return await audited_or_error(
        result, request, user, "delete_camera", payload.model_dump()
    )


@router.post("/create_roi", summary="Tạo / ghi đè ROI — node phải thuộc observedNodeIds")
async def create_roi(
    payload: CreateRoiPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.create_roi_v1.execute(
        payload.cameraId, payload.nodeId, payload.box
    )
    return await audited_or_error(
        result, request, user, "create_roi", payload.model_dump()
    )


@router.patch("/update_roi", summary="Cập nhật box ROI (batch qua items[])")
async def update_roi(
    payload: UpdateRoiPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    items = [item.model_dump() for item in (payload.items or [])]
    result = await container.update_roi_v1.execute(items)
    return await audited_or_error(
        result, request, user, "update_roi", {"items": items}
    )


@router.post("/delete_roi", summary="Xoá ROI khỏi camera doc")
async def delete_roi(
    payload: DeleteRoiPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.delete_roi_v1.execute(
        camera_id=payload.cameraId,
        node_id=payload.nodeId,
        roi_id=payload.id,
    )
    return await audited_or_error(
        result, request, user, "delete_roi", payload.model_dump()
    )
