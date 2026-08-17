"""Camera routes — presentation maps use case results to HTTP."""
from typing import Any, Dict
from fastapi import APIRouter, Body, Path

from application.container import container
from presentation.http import to_http, to_http_or_data, to_http_status

router = APIRouter(prefix="/cameras", tags=["cameras"])


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
