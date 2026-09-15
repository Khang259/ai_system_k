"""Request/Response schemas — Pydantic models for API layer."""
from pydantic import BaseModel, Field, model_validator
from typing import Any, List, Optional


class DetectionPayload(BaseModel):
    node_id:  str
    detected: bool


class WebhookPayload(BaseModel):
    orderId: str
    status:  int


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


class SetLockPayload(BaseModel):
    nodeId: str
    user: bool = True


class UnlockPayload(BaseModel):
    nodeId: str
    user: bool = False
    system: bool = False


class CameraConfigCreate(BaseModel):
    pass  # accepts any dict — validated at MongoDB level
    class Config:
        extra = "allow"


class CameraConfigUpdate(BaseModel):
    class Config:
        extra = "allow"
