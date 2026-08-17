"""Node routes — presentation maps use case results to HTTP."""
from typing import Any, Dict
from fastapi import APIRouter, Body

from application.container import container
from presentation.http import to_http

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/zone/{zone_id}")
async def get_nodes_by_zone(zone_id: str) -> Dict[str, Any]:
    return to_http(await container.get_nodes_by_zone.execute(zone_id))


@router.get("/{node_id}")
async def get_node(node_id: str) -> Dict[str, Any]:
    return to_http(await container.get_node_by_id.execute(node_id))


@router.post("/{node_id}/enable")
async def enable_node(node_id: str) -> Dict[str, Any]:
    return to_http(await container.set_node_enabled.execute(node_id, True))


@router.post("/{node_id}/disable")
async def disable_node(node_id: str) -> Dict[str, Any]:
    return to_http(await container.set_node_enabled.execute(node_id, False))


@router.put("/{node_id}/priority")
async def update_priority(
    node_id: str,
    priority: int = Body(..., embed=True),
) -> Dict[str, Any]:
    return to_http(await container.update_node_priority.execute(node_id, priority))


@router.post("/")
async def create_node(doc: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return to_http(await container.create_node.execute(doc))


@router.delete("/{node_id}")
async def delete_node(node_id: str) -> Dict[str, Any]:
    return to_http(await container.delete_node.execute(node_id))
