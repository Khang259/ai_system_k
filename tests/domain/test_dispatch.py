"""Unit tests — priority & pairing."""

from domain.dispatch.pairing import build_dispatch_pairs
from domain.dispatch.priority import resolve_priority, start_sort_key
from domain.settings import PRIORITY_FALLBACK


def test_resolve_priority_and_fallback():
    assert resolve_priority(3) == 3
    assert resolve_priority("5") == 5
    assert resolve_priority(None) == PRIORITY_FALLBACK
    assert resolve_priority("x") == PRIORITY_FALLBACK


def test_start_sort_key_uses_meta():
    meta = {
        "start_a": {"priority": 2, "zone_id": "B"},
        "start_b": {"priority": 1, "zone_id": "A"},
    }
    assert start_sort_key("start_b", meta) < start_sort_key("start_a", meta)


def test_build_dispatch_pairs_respects_mongo_priority():
    ready_starts = {"start_200", "start_100"}
    ready_ends = {"end_1", "end_2"}
    validate = [
        ("start_200", "end_2"),
        ("start_100", "end_1"),
    ]
    meta = {
        "start_100": {"priority": 1, "zone_id": "AE5"},
        "start_200": {"priority": 2, "zone_id": "AE5"},
    }

    pairs = build_dispatch_pairs(ready_starts, ready_ends, validate, meta)

    assert pairs == [("start_100", "end_1"), ("start_200", "end_2")]


def test_build_dispatch_pairs_cross_zone_same_priority_stable():
    """Cùng priority khác zone — thứ tự ổn định theo zone_id (không mang nghĩa NV)."""
    ready_starts = {"start_b", "start_a"}
    ready_ends = {"end_a", "end_b"}
    validate = [
        ("start_b", "end_b"),
        ("start_a", "end_a"),
    ]
    meta = {
        "start_a": {"priority": 1, "zone_id": "A"},
        "start_b": {"priority": 1, "zone_id": "B"},
    }

    pairs = build_dispatch_pairs(ready_starts, ready_ends, validate, meta)
    assert pairs == [("start_a", "end_a"), ("start_b", "end_b")]


def test_build_dispatch_pairs_missing_meta_uses_fallback():
    ready_starts = {"start_known", "start_unknown"}
    ready_ends = {"end_1", "end_2"}
    validate = [
        ("start_unknown", "end_2"),
        ("start_known", "end_1"),
    ]
    meta = {"start_known": {"priority": 1, "zone_id": "AE5"}}

    pairs = build_dispatch_pairs(ready_starts, ready_ends, validate, meta)
    assert pairs == [("start_known", "end_1"), ("start_unknown", "end_2")]


def test_build_dispatch_pairs_skips_len_one_and_missing_end():
    ready_starts = {"start_1", "start_empty"}
    ready_ends = {"end_9"}
    validate = [
        ("start_empty",),
        ("start_1", "end_missing"),
        ("start_1", "end_9"),
    ]
    meta = {"start_1": {"priority": 1, "zone_id": "AE5"}}

    pairs = build_dispatch_pairs(ready_starts, ready_ends, validate, meta)
    assert pairs == [("start_1", "end_9")]
