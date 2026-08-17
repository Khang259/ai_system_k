"""Runtime and health routes."""
from typing import Dict

from fastapi import APIRouter

from application.container import container
from presentation.http import to_http, to_http_or_data

router = APIRouter(tags=["runtime"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "AMR Camera System"}


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
