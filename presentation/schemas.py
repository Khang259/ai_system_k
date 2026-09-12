"""Request/Response schemas — Pydantic models for API layer."""
from pydantic import BaseModel, Field
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


class UpdateRoiPayload(BaseModel):
    box: List[float] = Field(..., min_length=4, max_length=4)
    id: Optional[str] = None
    cameraId: Optional[int] = None
    nodeId: Optional[str] = None


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
