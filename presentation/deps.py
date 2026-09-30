"""
Dependency xác thực cho nhóm `/api/v1`.

Chỉ nhóm này bắt token (chốt 2026-09-09). Ngoại lệ không Bearer:
- `POST /api/v1/nodes/unlock_by_order` (webhook ICS/AMR)

EventSource (SSE) không gửi Authorization header → dùng `current_user_sse`
(cho phép `?access_token=`). Các API CRUD khác chỉ Bearer.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from application.container import container

# auto_error=False → tự raise message tiếng Việt; đồng thời hiện Authorize trên /docs
_bearer = HTTPBearer(auto_error=False)


def client_info(request: Request) -> Tuple[str, str]:
    """(ip, user_agent) để ghi audit log."""
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "")
    return ip, request.headers.get("User-Agent") or ""


def _claims_from_token(token: str) -> Dict[str, Any]:
    claims = container.token_issuer.decode_access(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")
    return {
        "user_id": claims.get("sub", ""),
        "username": claims.get("username", ""),
        "role": claims.get("role", ""),
        "permissions": list(claims.get("permissions") or []),
    }


def _bearer_token(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    if creds is not None and (creds.credentials or "").strip():
        return creds.credentials.strip()
    raise HTTPException(status_code=401, detail="Thiếu Bearer token")


def _sse_token(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    access_token: Optional[str] = Query(
        None,
        description="JWT khi EventSource không gửi Authorization header",
    ),
) -> str:
    if creds is not None and (creds.credentials or "").strip():
        return creds.credentials.strip()
    if access_token and access_token.strip():
        return access_token.strip()
    raise HTTPException(status_code=401, detail="Thiếu Bearer token")


def current_user(token: str = Depends(_bearer_token)) -> Dict[str, Any]:
    """
    Giải mã access token từ Authorization Bearer — không query `access_token`.

    Đổi quyền chỉ có hiệu lực sau khi token cũ hết hạn (tối đa
    ACCESS_TOKEN_TTL_MIN). Đó là cái giá của việc không tra DB mỗi request.
    """
    return _claims_from_token(token)


def current_user_sse(token: str = Depends(_sse_token)) -> Dict[str, Any]:
    """Auth cho SSE: Bearer hoặc `?access_token=`."""
    return _claims_from_token(token)


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
