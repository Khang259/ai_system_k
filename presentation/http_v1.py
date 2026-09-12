"""
Vỏ HTTP cho nhóm /api/v1 — chuẩn frontend.

Khác `presentation/http.py` ở hai điểm: lỗi trả **HTTP status thật** kèm
`{"message": ...}` thay vì 200 kèm `{"success": false}`, và thành công trả
**data trần** không bọc `success`.

Nhóm route cũ giữ nguyên `http.py`, không đổi dòng nào.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException
from fastapi.responses import Response

from application.result import UseCaseResult


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


def jpeg_or_error(result: UseCaseResult, fail_status: int = 400) -> Response:
    """JPEG binary khi thành công; HTTPException (→ `{"message"}`) khi lỗi."""
    if result.success:
        return Response(content=result.data["jpeg"], media_type="image/jpeg")

    status = int(result.data.get("http_status") or fail_status)
    raise HTTPException(status_code=status, detail=result.error or "Request failed")


def paged(items: List[Any], total: int, page: int, page_size: int) -> Dict[str, Any]:
    """Vỏ phân trang FE mong đợi. Dùng cho logs / notifications."""
    return {"items": items, "total": total, "page": page, "pageSize": page_size}
