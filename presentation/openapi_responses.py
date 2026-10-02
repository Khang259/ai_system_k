"""
OpenAPI `responses` dùng chung cho `/api/v1`.

Chỉ là metadata Swagger — không ảnh hưởng runtime. Route import constant
thay vì nhồi dict inline.
"""
from __future__ import annotations

from typing import Any, Dict


def _desc(description: str) -> Dict[str, Any]:
    return {"description": description}


def merge(*parts: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Gộp nhiều khối status; key sau ghi đè key trước."""
    out: Dict[int, Dict[str, Any]] = {}
    for part in parts:
        out.update(part)
    return out


# --- Atom ---

AUTH_401: Dict[int, Dict[str, Any]] = {
    401: _desc("Thiếu / sai token"),
}
PERM_403: Dict[int, Dict[str, Any]] = {
    403: _desc("Thiếu quyền"),
}
# Gắn tại app.include_router(..., prefix=..., tags=..., responses=AUTH)
AUTH: Dict[int, Dict[str, Any]] = merge(AUTH_401, PERM_403)

BAD_REQUEST: Dict[int, Dict[str, Any]] = {400: _desc("Request / nghiệp vụ sai")}
NOT_FOUND: Dict[int, Dict[str, Any]] = {404: _desc("Không tìm thấy")}
CONFLICT: Dict[int, Dict[str, Any]] = {409: _desc("Xung đột trạng thái")}
RUNTIME_503: Dict[int, Dict[str, Any]] = {
    503: _desc("Runtime chưa sẵn sàng"),
}

# --- Auth ---

LOGIN = merge(
    {401: _desc("Sai username hoặc mật khẩu")},
    {403: _desc("Tài khoản bị vô hiệu hoá")},
    {429: _desc("Quá nhiều lần sai — tạm khoá")},
)
REFRESH_TOKEN = {
    401: _desc("Refresh token sai / hết hạn / tài khoản bị tắt"),
}

# --- Cameras / WebRTC ---

PREVIEW_META = merge(
    {200: _desc("rois + dets[{cls,conf,xyxy}] + ts")},
    {404: _desc("Camera not found")},
    {409: _desc("Camera not streaming")},
    {503: _desc("No meta yet")},
)

WHEP_CONNECT = merge(
    {201: {"description": "SDP answer", "content": {"application/sdp": {}}}},
    {404: _desc("Camera / RTSP not found")},
    {409: _desc("Max 4 sessions")},
    {503: _desc("MediaMTX chưa sẵn sàng")},
)

WHEP_DETECT = merge(
    {201: {"description": "SDP answer", "content": {"application/sdp": {}}}},
    {409: _desc("Max 4 sessions")},
    {503: _desc("MediaMTX chưa sẵn sàng")},
)

WHEP_HANGUP = merge(
    {200: _desc("Session closed")},
    {404: _desc("Session not found")},
)

JPEG_SNAPSHOT = merge(
    {200: {"description": "image/jpeg", "content": {"image/jpeg": {}}}},
    {404: _desc("Camera không tồn tại")},
    {409: _desc("Camera chưa streaming")},
    {503: _desc("Runtime chưa sẵn sàng / chưa có frame")},
)

# --- Zones / system / runtime ---

ZONE_START_STOP = merge(RUNTIME_503)  # 401/403 từ router AUTH

SYSTEM_START_ALL = {
    503: _desc("Runtime / model chưa sẵn sàng, hoặc không camera nào streaming"),
}
SYSTEM_STOP_ALL = merge(RUNTIME_503)

HEALTH = merge(
    {200: _desc("status=ok")},
    {503: _desc("status=degraded — vẫn trả mongo/runtime/webrtc trong body")},
)

CONFIRM_READY = merge(
    {400: _desc("Runtime chưa sẵn sàng / chưa start camera")},
)

SSE_EVENTS = merge(
    {200: {"description": "text/event-stream", "content": {"text/event-stream": {}}}},
    {401: _desc("Thiếu / sai token (header Bearer hoặc ?access_token=)")},
)

# --- Nodes / poll ---

RUNTIME_STATE = {
    200: _desc("runtimeReady + items (rỗng nếu runtime chưa sẵn — không 500)"),
}

UNLOCK_BY_SYSTEM = merge(
    {200: _desc("Đã reset theo status 3|23")},
    {
        400: _desc(
            "orderId không tìm thấy / status không hợp lệ / runtime chưa sẵn"
        )
    },
)

POLL_SNAPSHOT = merge(
    {200: _desc("Trạng thái hiện tại + etag + pollIntervalSec")},
    {304: _desc("Không đổi so với If-None-Match")},
)
