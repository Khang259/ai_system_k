"""ICS getOrderList adapter — POST {"areaId": N}, trả data.Tasks (trang 1)."""
from __future__ import annotations

from typing import Any, Dict, List

import requests


class HttpOrderQuery:
    def __init__(self, url: str, timeout: float = 5.0) -> None:
        self.url = url
        self.timeout = timeout

    def get_order_list(self, area_id: int) -> List[Dict[str, Any]]:
        resp = requests.post(self.url, json={"areaId": area_id}, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 1000:
            raise RuntimeError(body.get("desc") or f"ICS code={body.get('code')}")
        return list((body.get("data") or {}).get("Tasks") or [])
