"""Map routes — `/api/v1/maps/*` (global zip versions)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from application.container import container
from domain.permissions import MAP_READ, MAP_WRITE
from presentation.deps import require_permission
from presentation.http_v1 import audited_or_error, data_or_error

router = APIRouter()


class SetActiveMapPayload(BaseModel):
    versionId: str


@router.post(
    "/import_map",
    summary="Upload zip map — validate …/compress.json, lưu nguyên zip, set active",
)
async def import_map(
    request: Request,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_permission(MAP_WRITE)),
) -> Dict[str, Any]:
    data = await file.read()
    result = await container.import_map_v1.execute(
        data, file.filename or "map.zip", user.get("username") or ""
    )
    return await audited_or_error(
        result,
        request,
        user,
        "import_map",
        {"filename": file.filename, "bytes": len(data)},
    )


@router.get("/list_map_versions", summary="Danh sách version (mới nhất trước)")
async def list_map_versions(
    _user: Dict[str, Any] = Depends(require_permission(MAP_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.list_map_versions_v1.execute())


@router.post("/set_active_map", summary="Restore — chọn version active")
async def set_active_map(
    payload: SetActiveMapPayload,
    request: Request,
    user: Dict[str, Any] = Depends(require_permission(MAP_WRITE)),
) -> Dict[str, Any]:
    result = await container.set_active_map_v1.execute(payload.versionId)
    return await audited_or_error(
        result, request, user, "set_active_map", payload.model_dump()
    )


@router.get(
    "/get_compress",
    summary="Lấy compress.json để FE render — mặc định bản active",
)
async def get_compress(
    versionId: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(MAP_READ)),
) -> Dict[str, Any]:
    return data_or_error(await container.get_compress_v1.execute(versionId))


@router.get(
    "/download_map_zip",
    summary="Tải lại file zip gốc (active hoặc versionId)",
    response_class=Response,
)
async def download_map_zip(
    versionId: Optional[str] = Query(None),
    _user: Dict[str, Any] = Depends(require_permission(MAP_READ)),
) -> Response:
    result = await container.download_map_zip_v1.execute(versionId)
    if not result.success:
        data_or_error(result)
    filename = result.data["filename"]
    return Response(
        content=result.data["content"],
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
