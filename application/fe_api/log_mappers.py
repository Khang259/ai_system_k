"""Map log/notification docs → shape FE + parse query thời gian."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote


def iso_utc(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_device(user_agent: str) -> str:
    """Rút gọn UA thô → chuỗi ngắn cho cột device (không cần thư viện ngoài)."""
    ua = user_agent or ""
    browser = "Browser"
    if "Edg/" in ua:
        browser = "Edge"
    elif "Chrome/" in ua:
        browser = "Chrome"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Safari/" in ua and "Chrome/" not in ua:
        browser = "Safari"

    os_name = "Unknown"
    if "Windows" in ua:
        os_name = "Windows"
    elif "Android" in ua:
        os_name = "Android"
    elif "iPhone" in ua or "iPad" in ua:
        os_name = "iOS"
    elif "Mac OS" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"
    return f"{browser} · {os_name}"


def map_audit(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "userName": doc.get("user") or "",
        "role": doc.get("role") or "",
        "action": doc.get("event") or "",
        "ipAddress": doc.get("ip") or "",
        "device": parse_device(doc.get("user_agent") or ""),
        "occurredAt": iso_utc(doc.get("created_at")),
    }


def map_user_action(doc: Dict[str, Any]) -> Dict[str, Any]:
    payload = doc.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    return {
        "id": doc.get("id"),
        "userName": doc.get("user") or "",
        "role": doc.get("role") or "",
        "action": doc.get("action") or "",
        "endpoint": doc.get("endpoint") or "",
        "ipAddress": doc.get("ip") or "",
        "status": doc.get("status"),
        "occurredAt": iso_utc(doc.get("created_at")),
        "changes": payload.get("changes"),
        "payload": payload,
    }


def map_dispatch(doc: Dict[str, Any]) -> Dict[str, Any]:
    duration_sec = doc.get("duration_sec")
    return {
        "id": doc.get("id") or doc.get("order_id"),
        "orderId": doc.get("order_id"),
        "action": "dispatch",
        "result": doc.get("status"),
        "errorMessage": doc.get("error_msg"),
        "startNodeId": doc.get("start_point"),
        "endNodeId": doc.get("end_point"),
        "zoneId": doc.get("zone_id"),
        "durationMs": int(duration_sec * 1000) if isinstance(duration_sec, (int, float)) else None,
        "occurredAt": iso_utc(doc.get("dispatched_at") or doc.get("created_at")),
        "externalSource": "ICS",
        "requestPayload": doc.get("request_payload"),
        "responsePayload": doc.get("response_payload"),
    }


def snapshot_image_url(filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    # Chỉ tên file — route get_image chặn path traversal
    safe = filename.replace("\\", "/").split("/")[-1]
    if not safe:
        return None
    return f"/api/v1/snapshots/get_image?file={quote(safe)}"


def map_notification(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "type": doc.get("type") or "info",
        "title": doc.get("title") or "",
        "message": doc.get("message") or "",
        "createdAt": iso_utc(doc.get("created_at")),
        "readAt": iso_utc(doc.get("read_at")),
        "meta": doc.get("meta") or {},
        "snapshotImageUrl": snapshot_image_url(doc.get("snapshot_file")),
    }
