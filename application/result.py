"""Use case result — presentation maps this to HTTP dict."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class UseCaseResult:
    success: bool
    error: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, **data: Any) -> UseCaseResult:
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str, **data: Any) -> UseCaseResult:
        return cls(success=False, error=error, data=data)

    def to_http(self) -> Dict[str, Any]:
        if not self.success:
            payload: Dict[str, Any] = {"success": False, **self.data}
            if self.error is not None:
                payload["error"] = self.error
            return payload
        return {"success": True, **self.data}
