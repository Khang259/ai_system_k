"""Unit tests — NodeState (no RTSP / model / Mongo)."""

from domain.node_state import NodeState
from domain.settings import (
    END_FLAG_RESET_AFTER_SEC,
    END_READY_AFTER_SEC,
    START_READY_AFTER_SEC,
)


class FakeClock:
    def __init__(self, start: float = 1_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_start_enters_ready_after_threshold():
    clock = FakeClock()
    state = NodeState([], time_fn=clock)

    state.get_state_nodes("start_100", True)
    state.process_starts()
    assert "start_100" not in state.ready_start_list

    clock.advance(START_READY_AFTER_SEC + 1)
    state.process_starts()
    assert "start_100" in state.ready_start_list


def test_start_leaves_ready_when_empty():
    clock = FakeClock()
    state = NodeState([], time_fn=clock)
    state.get_state_nodes("start_100", True)
    clock.advance(START_READY_AFTER_SEC + 1)
    state.process_starts()
    assert "start_100" in state.ready_start_list

    state.get_state_nodes("start_100", False)
    assert "start_100" not in state.ready_start_list


def test_end_enters_ready_after_empty_threshold():
    clock = FakeClock()
    state = NodeState([], time_fn=clock)

    # end trống (state=False) — defaultdict starts False, set explicitly + time
    state.get_state_nodes("end_200", True)
    state.get_state_nodes("end_200", False)
    state.process_ends()
    assert "end_200" not in state.ready_end_list

    clock.advance(END_READY_AFTER_SEC + 1)
    state.process_ends()
    assert "end_200" in state.ready_end_list


def test_set_pair_used_sets_flags_and_mappings():
    state = NodeState([])
    state.get_state_nodes("start_1", True)
    state.get_state_nodes("end_2", False)
    state.ready_start_list.add("start_1")
    state.ready_end_list.add("end_2")

    state.set_pair_used("start_1", "end_2", "ORD-1", empty_car=False)

    assert state.points["start_1"]["flag"] is True
    assert state.points["end_2"]["flag"] is True
    assert "start_1" not in state.ready_start_list
    assert "end_2" not in state.ready_end_list
    assert state.pair_mapping["end_2"] == "start_1"
    assert state.order_mapping["ORD-1"] == [("start_1", "end_2", False)]


def test_process_ends_resets_flagged_pair_after_timeout():
    clock = FakeClock()
    state = NodeState([], time_fn=clock)
    state.set_pair_used("start_1", "end_2", "ORD-1")
    # End có hàng trở lại
    state.get_state_nodes("end_2", True)

    clock.advance(END_FLAG_RESET_AFTER_SEC + 1)
    state.process_ends()

    assert state.points["start_1"]["flag"] is False
    assert state.points["end_2"]["flag"] is False
    assert "end_2" not in state.pair_mapping
