"""ICS HTTP adapter — POST + retry. Application/domain không import requests."""
from __future__ import annotations

import time
from typing import Any, Dict

import requests

from utils.setup_log import setup_logger

logger = setup_logger("ics_gateway", "logs/ics_gateway/log")


class HttpDispatchGateway:
    def __init__(
        self,
        ics_url: str,
        retry: int = 3,
        delay: float = 1.0,
        timeout: float = 5.0,
    ) -> None:
        self.ics_url = ics_url
        self.retry = retry
        self.delay = delay
        self.timeout = timeout

    def send(self, payload: Dict[str, Any]) -> bool:
        for attempt in range(self.retry):
            try:
                resp = requests.post(self.ics_url, json=payload, timeout=self.timeout)
                if resp.status_code == 200 and resp.json().get("code") == 1000:
                    return True
                logger.error(
                    f"ICS attempt {attempt + 1}: bad response {resp.status_code}"
                )
            except Exception as e:
                logger.error(f"ICS attempt {attempt + 1}: {e}")
            time.sleep(self.delay)
        return False
