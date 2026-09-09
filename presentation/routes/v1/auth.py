"""Auth routes — `/api/v1/auth/*`."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, Response

from application.container import container
from presentation.deps import client_info, current_user
from presentation.http_v1 import data_or_error
from presentation.schemas import LoginPayload, RefreshPayload

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/login",
    summary="Đăng nhập — trả access token (ngắn hạn) + refresh token",
    responses={
        401: {"description": "Sai username hoặc mật khẩu"},
        403: {"description": "Tài khoản bị vô hiệu hoá"},
        429: {"description": "Quá nhiều lần sai — tạm khoá"},
    },
)
async def login(payload: LoginPayload, request: Request) -> Dict[str, Any]:
    ip, user_agent = client_info(request)
    return data_or_error(
        await container.login.execute(payload.username, payload.password, ip, user_agent)
    )


@router.post(
    "/logout",
    status_code=204,
    summary="Đăng xuất — thu hồi refresh token phía server",
)
async def logout(
    request: Request, user: Dict[str, Any] = Depends(current_user)
) -> Response:
    ip, _ = client_info(request)
    data_or_error(
        await container.logout.execute(user["user_id"], user["username"], ip)
    )
    return Response(status_code=204)


@router.get("/get_me", summary="User hiện tại — khôi phục session khi refresh trang")
async def get_me(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return data_or_error(await container.get_me.execute(user["user_id"]))


@router.post(
    "/refresh_token",
    summary="Gia hạn phiên — cấp cặp token mới, token cũ hết hiệu lực ngay",
    responses={401: {"description": "Refresh token sai / hết hạn / tài khoản bị tắt"}},
)
async def refresh_token(payload: RefreshPayload) -> Dict[str, Any]:
    return data_or_error(await container.refresh_session.execute(payload.refreshToken))
