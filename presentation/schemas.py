"""Request/Response schemas — Pydantic models for API layer."""
from pydantic import BaseModel, Field, model_validator
from typing import Any, List, Optional


class LoginPayload(BaseModel):
    username: str
    password: str


class RefreshPayload(BaseModel):
    # camelCase theo FE, không đổi sang snake_case
    refreshToken: str


class ZoneControlPayload(BaseModel):
    zoneId: str


class SetCameraStatusPayload(BaseModel):
    cameraId: int
    enabled: bool


class UpdateCameraPayload(BaseModel):
    """Partial update — ít nhất một trong name / rtspUrl / zone / observedNodeIds."""
    cameraId: int
    name: Optional[str] = None
    rtspUrl: Optional[str] = None
    zone: Optional[str] = None
    observedNodeIds: Optional[List[str]] = None


class CreateCameraPayload(BaseModel):
    name: str
    rtspUrl: str
    zone: Optional[str] = None
    observedNodeIds: Optional[List[str]] = None


class DeleteCameraPayload(BaseModel):
    cameraId: int


class CreateRoiPayload(BaseModel):
    cameraId: int
    nodeId: str
    box: List[float] = Field(..., min_length=4, max_length=4)


class UpdateRoiItemPayload(BaseModel):
    """Một ROI trong batch update."""
    box: List[float] = Field(..., min_length=4, max_length=4)
    id: Optional[str] = None
    cameraId: Optional[int] = None
    nodeId: Optional[str] = None


class UpdateRoiPayload(BaseModel):
    """
    Batch: `{ "items": [ { id|cameraId+nodeId, box }, ... ] }`.
    Single (tương thích cũ): `{ "id", "box" }` hoặc `{ cameraId, nodeId, box }`.
    """
    items: Optional[List[UpdateRoiItemPayload]] = Field(None, min_length=1)
    box: Optional[List[float]] = Field(None, min_length=4, max_length=4)
    id: Optional[str] = None
    cameraId: Optional[int] = None
    nodeId: Optional[str] = None

    @model_validator(mode="after")
    def normalize_items(self) -> "UpdateRoiPayload":
        if self.items:
            return self
        if self.box is not None:
            self.items = [
                UpdateRoiItemPayload(
                    box=self.box,
                    id=self.id,
                    cameraId=self.cameraId,
                    nodeId=self.nodeId,
                )
            ]
            return self
        raise ValueError("Cần items[] hoặc (box + id|cameraId+nodeId)")


class DeleteRoiPayload(BaseModel):
    id: Optional[str] = None
    cameraId: Optional[int] = None
    nodeId: Optional[str] = None


class SetMaintenancePayload(BaseModel):
    nodeId: str
    isUnderMaintenance: bool
    maintenanceReason: Optional[str] = None


class UpdateNodePayload(BaseModel):
    nodeId: str
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    zoneId: Optional[str] = None
    cameraId: Optional[int] = None


class DeleteNodePayload(BaseModel):
    nodeId: str


class CreatePairPayload(BaseModel):
    startNodeId: str
    zoneId: str
    pairType: str = "normal"
    endNodeId: Optional[str] = None
    enabled: bool = True
    autoDispatch: bool = True
    name: Optional[str] = None


class UpdatePairPayload(BaseModel):
    """Partial update — ít nhất một field ngoài id."""
    id: str
    startNodeId: Optional[str] = None
    endNodeId: Optional[str] = None
    zoneId: Optional[str] = None
    pairType: Optional[str] = None
    enabled: Optional[bool] = None
    autoDispatch: Optional[bool] = None
    name: Optional[str] = None

    @model_validator(mode="after")
    def require_mutable_field(self) -> "UpdatePairPayload":
        if any(
            v is not None
            for v in (
                self.startNodeId,
                self.endNodeId,
                self.zoneId,
                self.pairType,
                self.enabled,
                self.autoDispatch,
                self.name,
            )
        ):
            return self
        raise ValueError("Cần ít nhất một field để sửa")


class DeletePairPayload(BaseModel):
    id: Optional[str] = None
    startNodeId: Optional[str] = None
    endNodeId: Optional[str] = None

    @model_validator(mode="after")
    def require_identity(self) -> "DeletePairPayload":
        if self.id or self.startNodeId:
            return self
        raise ValueError("Cần id hoặc startNodeId")


class SetPairEnabledPayload(BaseModel):
    id: Optional[str] = None
    startNodeId: Optional[str] = None
    endNodeId: Optional[str] = None
    enabled: bool

    @model_validator(mode="after")
    def require_identity(self) -> "SetPairEnabledPayload":
        if self.id or self.startNodeId:
            return self
        raise ValueError("Cần id hoặc startNodeId")


class SetLockPayload(BaseModel):
    nodeId: str
    user: bool = True


class UnlockPayload(BaseModel):
    nodeId: str
    user: bool = False
    system: bool = False


class UnlockByOrderPayload(BaseModel):
    """External/ICS — reset system lock theo orderId (status 3|23)."""

    orderId: str
    status: int  # 3 = COMPLETED (toàn bộ), 23 = EMPTY_DONE (chỉ empty)


class CameraConfigCreate(BaseModel):
    pass  # accepts any dict — validated at MongoDB level
    class Config:
        extra = "allow"


class CameraConfigUpdate(BaseModel):
    class Config:
        extra = "allow"
