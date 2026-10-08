from domain.dispatch.active_task import (
    build_active_task,
    parse_order_id,
    sort_active_tasks,
    status_label,
)

ORDER = "S-10000061-10000761-2026-10-03 09:51:33.123456"


def test_parse_order_id_keeps_datetime_suffix():
    assert parse_order_id(ORDER) == ("start_10000061", "end_10000761")


def test_parse_order_id_rejects_other_formats():
    assert parse_order_id("RCS-44-1790995893186") is None
    assert parse_order_id("99999930") is None
    assert parse_order_id(None) is None


def test_status_label_only_issued_and_inprogress():
    assert status_label(9) == "issued"
    assert status_label(6) == "inprogress"
    assert status_label(3) is None  # clear panel — không map label FE
    assert status_label(23) is None
    assert status_label("x") is None


def test_build_active_task_uses_start_priority():
    item = build_active_task(ORDER, "issued", {"start_10000061": {"priority": 2}})
    assert item == {
        "orderId": ORDER,
        "startNodeId": "start_10000061",
        "endNodeId": "end_10000761",
        "priorityStart": 2,
        "status": "issued",
    }


def test_sort_active_tasks_missing_priority_last():
    items = [
        {"orderId": "b", "priorityStart": None},
        {"orderId": "c", "priorityStart": 2},
        {"orderId": "a", "priorityStart": 1},
    ]
    assert [it["orderId"] for it in sort_active_tasks(items)] == ["a", "c", "b"]
