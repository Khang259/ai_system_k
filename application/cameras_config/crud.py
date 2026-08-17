from typing import Any, Dict

from application.result import UseCaseResult
from application.ports import CameraConfigRepository


class ListCameraConfigs:
    def __init__(self, repo: CameraConfigRepository) -> None:
        self._repo = repo

    async def execute(self) -> UseCaseResult:
        items = await self._repo.get_all()
        return UseCaseResult.ok(items=items)


class ListCameraConfigsByArea:
    def __init__(self, repo: CameraConfigRepository) -> None:
        self._repo = repo

    async def execute(self, area: str) -> UseCaseResult:
        items = await self._repo.get_by_area(area)
        return UseCaseResult.ok(area=area.upper(), items=items)


class CreateCameraConfig:
    def __init__(self, repo: CameraConfigRepository) -> None:
        self._repo = repo

    async def execute(self, doc: Dict[str, Any]) -> UseCaseResult:
        inserted_id = await self._repo.create(doc)
        return UseCaseResult.ok(inserted_id=inserted_id)


class UpdateCameraConfig:
    def __init__(self, repo: CameraConfigRepository) -> None:
        self._repo = repo

    async def execute(self, camera_id: int, data: Dict[str, Any]) -> UseCaseResult:
        ok = await self._repo.update_by_camera_id(camera_id, data)
        return UseCaseResult(success=ok, data={"cameraId": camera_id})


class DeleteCameraConfig:
    def __init__(self, repo: CameraConfigRepository) -> None:
        self._repo = repo

    async def execute(self, camera_id: int) -> UseCaseResult:
        ok = await self._repo.delete_by_camera_id(camera_id)
        return UseCaseResult(success=ok, data={"cameraId": camera_id})
