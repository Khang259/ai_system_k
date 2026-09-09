"""Request/Response schemas — Pydantic models for API layer."""
from pydantic import BaseModel
from typing import Any, Dict, Optional


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


class CameraConfigCreate(BaseModel):
    pass  # accepts any dict — validated at MongoDB level
    class Config:
        extra = "allow"


class CameraConfigUpdate(BaseModel):
    class Config:
        extra = "allow"
