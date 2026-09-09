"""
Dependency xác thực cho nhóm `/api/v1`.

Chỉ nhóm này bắt token (chốt 2026-09-09). Route cũ giữ mở để webhook ICS
(`/delete-flag`) và thiết bị đẩy detection (`/detections`) không bị chặn.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from fastapi import Depends, HTTPException, Request

from application.container import container


def client_info(request: Request) -> Tuple[str, str]:
    """(ip, user_agent) để ghi audit log."""
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "")
    return ip, request.headers.get("User-Agent") or ""


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Thiếu Bearer token")
    return token.strip()


def current_user(request: Request) -> Dict[str, Any]:
    """
    Giải mã access token, không truy vấn Mongo.

    Đổi lại: quyền vừa bị sửa chỉ có hiệu lực sau khi token cũ hết hạn (tối đa
    ACCESS_TOKEN_TTL_MIN). Đó là cái giá của việc không tra DB mỗi request.
    """
    claims = container.token_issuer.decode_access(_bearer_token(request))
    if claims is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")

    return {
        "user_id": claims.get("sub", ""),
        "username": claims.get("username", ""),
        "role": claims.get("role", ""),
        "permissions": list(claims.get("permissions") or []),
    }


def require_permission(permission: str):
    """
    Chặn theo mảng `permissions` trong token, **không** theo role.

    FE cũng cam kết không hardcode role, nên thêm/bớt quyền chỉ là sửa dữ liệu
    user, không phải sửa code hai phía.
    """

    def _check(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
        if permission not in user["permissions"]:
            raise HTTPException(status_code=403, detail=f"Thiếu quyền: {permission}")
        return user

    return _check
