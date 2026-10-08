"""
Vỏ HTTP cho nhóm /api/v1 — chuẩn frontend.

Lỗi trả HTTP status thật kèm `{"message": ...}`; thành công trả data trần
(không bọc `success`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request
from fastapi.responses import Response

from application.container import container
from application.result import UseCaseResult
from presentation.deps import client_info


def data_or_error(result: UseCaseResult, fail_status: int = 400) -> Dict[str, Any]:
    """
    Trả `result.data` khi thành công; raise HTTPException khi thất bại.

    Use case đặt `http_status` vào data để chọn mã lỗi (401, 409...); không có
    thì dùng `fail_status`. Handler ở app.py đổi `detail` thành `message`.
    """
    if result.success:
        return result.data

    status = int(result.data.get("http_status") or fail_status)
    raise HTTPException(status_code=status, detail=result.error or "Request failed")


async def audited_or_error(
    result: UseCaseResult,
    request: Request,
    user: Optional[Dict[str, Any]],
    action: str,
    payload: Dict[str, Any],
    *,
    fail_status: int = 400,
    audit_user: Optional[str] = None,
    audit_role: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ghi user-action log rồi map result → HTTP (thin route: execute → return).

    `audit_user` / `audit_role` ghi đè khi không có JWT.
    """
    status = 200 if result.success else int(result.data.get("http_status") or fail_status)
    ip, _ = client_info(request)
    if audit_user is not None:
        uname, role = audit_user, audit_role or ""
    else:
        u = user or {}
        uname = u.get("username") or u.get("user_id") or ""
        role = u.get("role") or ""
    await container.action_audit.log(
        user=uname,
        role=role,
        action=action,
        endpoint=str(request.url.path),
        payload=payload,
        ip=ip,
        status=status,
    )
    return data_or_error(result, fail_status=fail_status)


async def system_audited_or_error(
    result: UseCaseResult,
    request: Request,
    action: str,
    payload: Dict[str, Any],
    *,
    order_id: Optional[str] = None,
    fail_status: int = 400,
) -> Dict[str, Any]:
    """Ghi system-action log (dispatch_logs) rồi map result → HTTP."""
    status = 200 if result.success else int(result.data.get("http_status") or fail_status)
    await container.system_action_audit.log(
        action=action,
        order_id=order_id,
        endpoint=str(request.url.path),
        payload=payload,
        status=status,
        result=result.data if result.success else None,
        error=None if result.success else (result.error or "Request failed"),
    )
    return data_or_error(result, fail_status=fail_status)


def jpeg_or_error(result: UseCaseResult, fail_status: int = 400) -> Response:
    """JPEG binary khi thành công; HTTPException (→ `{"message"}`) khi lỗi."""
    if result.success:
        return Response(content=result.data["jpeg"], media_type="image/jpeg")

    status = int(result.data.get("http_status") or fail_status)
    raise HTTPException(status_code=status, detail=result.error or "Request failed")


def sdp_or_error(
    result: UseCaseResult,
    *,
    location: str,
    fail_status: int = 503,
) -> Response:
    """WHEP: 201 + application/sdp + Location; lỗi → HTTPException + message."""
    if result.success:
        return Response(
            content=result.data["sdp"],
            media_type="application/sdp",
            status_code=201,
            headers={"Location": location},
        )

    status = int(result.data.get("http_status") or fail_status)
    raise HTTPException(status_code=status, detail=result.error or "Request failed")


def paged(items: List[Any], total: int, page: int, page_size: int) -> Dict[str, Any]:
    """Vỏ phân trang FE mong đợi. Dùng cho logs / notifications."""
    return {"items": items, "total": total, "page": page, "pageSize": page_size}
