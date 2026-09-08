"""Runtime and health routes."""
from fastapi import APIRouter

from application.container import container
from presentation.http import to_http, to_http_or_data, to_http_status

router = APIRouter(tags=["runtime"])


@router.get("/health")
async def health_check():
    """200 khi Mongo + runtime OK; 503 khi degraded. MediaMTX chỉ report."""
    return to_http_status(await container.get_health.execute())


@router.get("/runtime/status")
async def get_runtime_status():
    return to_http_or_data(container.get_runtime_status.execute())


@router.post("/runtime/reload")
async def reload_runtime():
    return to_http_or_data(await container.reload_runtime.execute())


@router.post("/runtime/confirm-ready")
async def confirm_ready():
    return to_http(container.confirm_ready.execute())


@router.post("/runtime/pause-scan")
async def pause_scan():
    return to_http(container.pause_scan.execute())
