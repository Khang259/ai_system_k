"""Camera routes — `/api/v1/cameras/*`."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from application.container import container
from domain.permissions import CAMERA_READ, CAMERA_WRITE
from presentation.deps import client_info, require_permission
from presentation.http_v1 import data_or_error, jpeg_or_error
from presentation.schemas import (
    CreateRoiPayload,
    DeleteCameraPayload,
    DeleteRoiPayload,
    SetCameraStatusPayload,
    UpdateCameraPayload,
    UpdateRoiPayload,
)

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras-v1"])


async def _audit(
    request: Request,
    user: Dict[str, Any],
    action: str,
    payload: Dict[str, Any],
    status: int,
) -> None:
    ip, _ = client_info(request)
    await container.action_audit.log(
        user=user.get("username") or user.get("user_id") or "",
        role=user.get("role") or "",
        action=action,
        endpoint=str(request.url.path),
        payload=payload,
        ip=ip,
        status=status,
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
    responses={
        200: {"content": {"image/jpeg": {}}},
        401: {"description": "Thiếu / sai token"},
        403: {"description": "Thiếu camera.read"},
        404: {"description": "Camera không tồn tại"},
        409: {"description": "Camera chưa streaming"},
        503: {"description": "Runtime chưa sẵn sàng / chưa có frame"},
    },
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
    await _audit(
        request,
        user,
        "set_camera_status",
        payload.model_dump(),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


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
    await _audit(
        request,
        user,
        "update_camera",
        payload.model_dump(exclude_none=True),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


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
    await _audit(
        request,
        user,
        "delete_camera",
        payload.model_dump(),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.post("/create_roi", summary="Tạo / ghi đè ROI — node phải thuộc observedNodeIds")
async def create_roi(
    payload: CreateRoiPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    result = await container.create_roi_v1.execute(
        payload.cameraId, payload.nodeId, payload.box
    )
    await _audit(
        request,
        user,
        "create_roi",
        payload.model_dump(),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


@router.patch("/update_roi", summary="Cập nhật box ROI (batch qua items[])")
async def update_roi(
    payload: UpdateRoiPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(CAMERA_WRITE)),
) -> Dict[str, Any]:
    items = [item.model_dump() for item in (payload.items or [])]
    result = await container.update_roi_v1.execute(items)
    await _audit(
        request,
        user,
        "update_roi",
        {"items": items},
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)


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
    await _audit(
        request,
        user,
        "delete_roi",
        payload.model_dump(),
        200 if result.success else int(result.data.get("http_status") or 400),
    )
    return data_or_error(result)
