"""Unit tests — priority & pairing."""

from domain.dispatch.pairing import build_dispatch_pairs
from domain.dispatch.priority import get_node_priority
from domain.settings import PRIORITY_FALLBACK


def test_get_node_priority_extracts_digits():
    assert get_node_priority("start_10001050") == 10001050
    assert get_node_priority("end_99") == 99


def test_get_node_priority_fallback():
    assert get_node_priority("start_abc") == PRIORITY_FALLBACK


def test_build_dispatch_pairs_respects_priority_and_validate():
    ready_starts = {"start_200", "start_100"}
    ready_ends = {"end_1", "end_2"}
    validate = [
        ("start_200", "end_2"),
        ("start_100", "end_1"),
    ]

    pairs = build_dispatch_pairs(ready_starts, ready_ends, validate)

    # start_100 priority thấp hơn số → đứng trước start_200
    assert pairs == [("start_100", "end_1"), ("start_200", "end_2")]


def test_build_dispatch_pairs_skips_len_one_and_missing_end():
    ready_starts = {"start_1", "start_empty"}
    ready_ends = {"end_9"}
    validate = [
        ("start_empty",),
        ("start_1", "end_missing"),
        ("start_1", "end_9"),
    ]

    pairs = build_dispatch_pairs(ready_starts, ready_ends, validate)
    assert pairs == [("start_1", "end_9")]
