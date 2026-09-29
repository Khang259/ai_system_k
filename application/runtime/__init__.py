"""Runtime control, health, and in-process state hub.

Singleton `runtime_service` import trực tiếp:
`from application.runtime.runtime_service import runtime_service`
(trùng tên submodule — không re-export qua barrel).
"""
from application.runtime.control import (
    GetRuntimeStatus,
    ReloadRuntime,
    StartRuntime,
    StopRuntime,
)
from application.runtime.health import GetHealth
from application.runtime.runtime_state_hub import RuntimeStateHub

__all__ = [
    "GetHealth",
    "GetRuntimeStatus",
    "ReloadRuntime",
    "RuntimeStateHub",
    "StartRuntime",
    "StopRuntime",
]
