"""Dispatch runtime — PairManager + strategies."""
from infrastructure.dispatch.pair_manager import (
    DoubleDispatch,
    EmptyDispatch,
    PairManager,
    SingleDispatch,
)

__all__ = [
    "PairManager",
    "SingleDispatch",
    "EmptyDispatch",
    "DoubleDispatch",
]
