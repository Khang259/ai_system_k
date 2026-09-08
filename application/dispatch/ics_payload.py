"""ICS JSON payload builders — một nguồn cho DispatchService."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from config.settings import settings


def _digits(node_id: str) -> str:
    return "".join(filter(str.isdigit, str(node_id)))


def build_single_payload(start_point: str, end_point: str) -> Dict[str, Any]:
    now = datetime.now()
    start_num = _digits(start_point)
    end_num = _digits(end_point)
    return {
        "modelProcessCode": settings.ICS_PROCESS_SINGLE,
        "fromSystem": "ICS",
        "orderId": f"S-{start_num}-{end_num}-{now}",
        "taskOrderDetail": [{"taskPath": f"{start_num},{end_num}"}],
    }


def build_empty_payload(start_point: str, end_point: str) -> Dict[str, Any]:
    now = datetime.now()
    start_num = _digits(start_point)
    end_num = _digits(end_point)
    return {
        "modelProcessCode": settings.ICS_PROCESS_EMPTY,
        "fromSystem": "ICS",
        "orderId": f"E-{start_num}-{now}",
        "taskOrderDetail": [{"taskPath": f"{start_num},{end_num}"}],
    }


def build_double_payload(
    start_point: str,
    end_point: str,
    start_empty: str,
    end_empty: str,
) -> Dict[str, Any]:
    now = datetime.now()
    start_num = _digits(start_point)
    end_num = _digits(end_point)
    start_empty_num = _digits(start_empty)
    end_empty_num = _digits(end_empty)
    return {
        "modelProcessCode": settings.ICS_PROCESS_DOUBLE,
        "fromSystem": "ICS",
        "orderId": f"D-AE-{start_num}-{end_num}-{start_empty_num}-{now}",
        "taskOrderDetail": [
            {"taskPath": f"{start_num},{end_num}"},
            {"taskPath": f"{start_empty_num},{end_empty_num}"},
        ],
    }
