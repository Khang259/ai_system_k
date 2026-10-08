"""
Smoke trail — log tạm cho sandbox, giúp đối chiếu checklist operator.

File: logs/sandbox/smoke_trail_YYYYMMDD.log
Chỉ ghi khi RUNTIME_MODE=sandbox; production = no-op.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config.settings import settings
from utils.setup_log import setup_logger

_logger = setup_logger("smoke_trail", "logs/sandbox/smoke_trail")


def _enabled() -> bool:
    return settings.RUNTIME_MODE == "sandbox"


def emit(source: str, action: str, **detail: Any) -> None:
    """
    source: api | system
    action: tên sự kiện (set_node_state, dispatch, batch_complete, …)
    """
    if not _enabled():
        return
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "action": action,
        **{k: v for k, v in detail.items() if v is not None},
    }
    _logger.info(json.dumps(row, ensure_ascii=False, default=str))


def node_runtime_view(state, *node_ids: str) -> Dict[str, Any]:
    """Snapshot detected/isReady/lock của vài node — phục vụ đối chiếu start/end."""
    if state is None or not getattr(state, "is_ready", lambda: False)():
        return {}
    try:
        snap = state.snapshot_points()
    except Exception:
        return {}
    out: Dict[str, Any] = {}
    for nid in node_ids:
        if not nid:
            continue
        p = snap.get(nid) or {}
        out[nid] = {
            "detected": p.get("detected"),
            "isReady": p.get("isReady"),
            "lock": p.get("lock"),
        }
    return out


def inference_paused(inference) -> Optional[bool]:
    if inference is None:
        return None
    try:
        if hasattr(inference, "is_paused"):
            return bool(inference.is_paused())
        paused = getattr(inference, "_paused", None)
        if paused is not None and hasattr(paused, "is_set"):
            return bool(paused.is_set())
    except Exception:
        return None
    return None
