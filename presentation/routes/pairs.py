"""Pairs routes — presentation maps use case results to HTTP."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Body

from application.container import container
from presentation.http import to_http

router = APIRouter(prefix="/pairs", tags=["pairs"])


@router.get("/zone/{zone_id}")
async def get_pairs_by_zone(zone_id: str) -> Dict[str, Any]:
    return to_http(await container.get_pairs_by_zone.execute(zone_id))


@router.post("/enable")
async def enable_pair(
    start_point: str = Body(...),
    end_point: Optional[str] = Body(None),
) -> Dict[str, Any]:
    return to_http(await container.set_pair_enabled.execute(start_point, end_point, True))


@router.post("/disable")
async def disable_pair(
    start_point: str = Body(...),
    end_point: Optional[str] = Body(None),
) -> Dict[str, Any]:
    return to_http(await container.set_pair_enabled.execute(start_point, end_point, False))


@router.post("/")
async def create_pair(doc: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return to_http(await container.create_pair.execute(doc))


@router.delete("/")
async def delete_pair(
    start_point: str = Body(...),
    end_point: Optional[str] = Body(None),
) -> Dict[str, Any]:
    return to_http(await container.delete_pair.execute(start_point, end_point))
