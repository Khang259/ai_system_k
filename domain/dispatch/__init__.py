"""Dispatch domain helpers — priority & pairing (no HTTP / ICS)."""

from domain.dispatch.priority import resolve_priority, start_sort_key
from domain.dispatch.pairing import build_dispatch_pairs

__all__ = ["resolve_priority", "start_sort_key", "build_dispatch_pairs"]
