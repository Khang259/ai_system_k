"""Unit tests — fill_cols_head_to_tail: head/tail fill + lock stop."""

from domain.batch_policy import fill_cols_head_to_tail

META = {
    f"start_{i}": {"priority": i, "zone_id": "Z1", "col_id": "A"} for i in range(1, 6)
}
META.update(
    {f"start_{i}": {"priority": i, "zone_id": "Z1", "col_id": "B"} for i in range(6, 9)}
)


def _ids(*nums):
    return {f"start_{n}" for n in nums}


def test_fill_between_head_and_tail():
    assert fill_cols_head_to_tail(_ids(1, 5), META) == _ids(1, 2, 3, 4, 5)


def test_empty_before_head_is_not_filled():
    assert fill_cols_head_to_tail(_ids(2, 5), META) == _ids(2, 3, 4, 5)


def test_single_ready_head_equals_tail():
    assert fill_cols_head_to_tail(_ids(3), META) == _ids(3)


def test_nothing_after_tail():
    assert fill_cols_head_to_tail(_ids(2, 4), META) == _ids(2, 3, 4)


def test_user_lock_between_stops_col():
    out = fill_cols_head_to_tail(_ids(1, 5), META, user_locked=_ids(3))
    assert out == _ids(1, 2)


def test_system_lock_between_stops_col():
    out = fill_cols_head_to_tail(_ids(1, 5), META, system_locked=_ids(3))
    assert out == _ids(1, 2)


def test_user_lock_before_head_drops_whole_col():
    out = fill_cols_head_to_tail(_ids(2, 5, 6, 8), META, user_locked=_ids(1))
    assert out == _ids(6, 7, 8)


def test_system_lock_before_head_does_not_block():
    out = fill_cols_head_to_tail(_ids(2, 5), META, system_locked=_ids(1))
    assert out == _ids(2, 3, 4, 5)


def test_cols_filled_independently():
    assert fill_cols_head_to_tail(_ids(1, 3, 6, 8), META) == _ids(1, 2, 3, 6, 7, 8)


def test_ready_without_meta_kept():
    assert fill_cols_head_to_tail({"start_99"}, META) == {"start_99"}
