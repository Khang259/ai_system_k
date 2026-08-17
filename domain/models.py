"""
Domain layer — pure Python models, no dependencies on DB or frameworks.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class NodeType(str, Enum):
    START = "start"
    END = "end"


class DispatchType(str, Enum):
    SINGLE = "single"      # 1 start → 1 end (có hàng)
    EMPTY  = "empty"       # 1 start trống → end cố định
    DOUBLE = "double"      # 1 start + 1 start_empty → 2 end cùng lúc


class ResetStatus(int, Enum):
    COMPLETED      = 3   # AMR hoàn thành toàn bộ → reset tất cả flag
    EMPTY_DONE     = 23  # AMR hoàn thành chuyến trống → chỉ reset empty


@dataclass
class NodePoint:
    node_id: str
    state: bool = False          # True = có hàng (start) | False = trống (end)
    flag: bool  = False          # True = đang được dispatch, chờ AMR xong
    frame: Optional[object] = None


@dataclass
class DispatchPair:
    start_point: str
    end_point: str
    order_id: str
    dispatch_type: DispatchType
    empty_car: bool = False


@dataclass
class RuntimeStatus:
    running: bool
    area: Optional[str]
    cameras_total: int
    cameras_enabled: int
    cameras_alive: int
    inference_paused: Optional[bool]
    started_at: Optional[float]
