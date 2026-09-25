"""Health ops ngoài `/api/v1` (GIỮ_ops). Runtime control chỉ còn `/api/v1/runtime/*`."""
from fastapi import APIRouter

from application.container import container
from presentation.http import to_http_status

router = APIRouter(tags=["runtime"])


@router.get("/health")
async def health_check():
    """200 khi Mongo + runtime OK; 503 khi degraded. MediaMTX chỉ report. Không Bearer."""
    return to_http_status(await container.get_health.execute())
