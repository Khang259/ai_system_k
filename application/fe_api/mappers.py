"""Map document Mongo → shape FE cho /api/v1 (camelCase)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def node_label(node_type: str, priority: int) -> str:
    """Sinh label tạm: S-01 / E-02. Đổi khi priority đổi (field Mongo đang hoãn)."""
    prefix = "S" if (node_type or "").lower() == "start" else "E"
    try:
        n = int(priority)
    except (TypeError, ValueError):
        n = 0
    return f"{prefix}-{n:02d}"


def camera_status(db_enabled: bool, runtime: Optional[Dict[str, Any]]) -> str:
    """
    disabled | offline | streaming.

    Khi runtime chưa sẵn sàng: enabled → offline, disabled → disabled.
    """
    if not db_enabled:
        return "disabled"
    if runtime is None:
        return "offline"
    if not runtime.get("enabled"):
        # Mongo bật nhưng RAM đang tắt (stop zone/system)
        return "offline"
    if runtime.get("streaming"):
        return "streaming"
    return "offline"


def parse_roi_id(roi_id: str) -> Optional[Tuple[int, str]]:
    """`{cameraId}:{nodeId}` → (cameraId, nodeId)."""
    if not roi_id or ":" not in roi_id:
        return None
    cam_s, node_id = roi_id.split(":", 1)
    try:
        return int(cam_s), node_id
    except ValueError:
        return None


def roi_item(
    camera_id: int,
    node_id: str,
    entry: Any,
    *,
    label: str,
    kind: str,
    ref_width: int,
    ref_height: int,
) -> Dict[str, Any]:
    box: List[float]
    if isinstance(entry, dict):
        box = list(entry.get("roi") or [])
        ref_w = int(entry.get("ref_width") or entry.get("refWidth") or ref_width)
        ref_h = int(entry.get("ref_height") or entry.get("refHeight") or ref_height)
        if entry.get("start"):
            kind = "start"
        elif entry.get("end"):
            kind = "end"
    elif isinstance(entry, (list, tuple)):
        box = list(entry)
        ref_w, ref_h = ref_width, ref_height
    else:
        box = []
        ref_w, ref_h = ref_width, ref_height

    return {
        "id": f"{camera_id}:{node_id}",
        "cameraId": camera_id,
        "nodeId": node_id,
        "label": label,
        "kind": kind,
        "box": box,
        "refWidth": ref_w,
        "refHeight": ref_h,
    }


def validate_box(
    box: List[Any], ref_width: int, ref_height: int
) -> Optional[str]:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return "box phải là [x, y, w, h]"
    try:
        x, y, w, h = (float(v) for v in box)
    except (TypeError, ValueError):
        return "box phải là số"
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return "box: x,y ≥ 0 và w,h > 0"
    if x + w > ref_width + 1e-6 or y + h > ref_height + 1e-6:
        return f"box vượt khung {ref_width}×{ref_height}"
    return None
