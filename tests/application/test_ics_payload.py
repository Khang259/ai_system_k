"""ICS payload builder — không HTTP."""
from application.dispatch.ics_payload import (
    build_double_payload,
    build_empty_payload,
    build_single_payload,
)


def test_build_single_payload():
    payload = build_single_payload("start_10001050", "end_10000759")
    assert payload["modelProcessCode"] == "SingleGroupAE5"
    assert payload["fromSystem"] == "ICS"
    assert payload["orderId"].startswith("S-10001050-10000759-")
    assert payload["taskOrderDetail"] == [{"taskPath": "10001050,10000759"}]


def test_build_empty_payload():
    payload = build_empty_payload("start_10000391", "end_10001546")
    assert payload["modelProcessCode"] == "SEGroupAE"
    assert payload["orderId"].startswith("E-10000391-")
    assert payload["taskOrderDetail"] == [{"taskPath": "10000391,10001546"}]


def test_build_double_payload():
    payload = build_double_payload(
        "start_100", "end_200", "start_300", "end_400"
    )
    assert payload["modelProcessCode"] == "DoubleGroupAE"
    assert payload["orderId"].startswith("D-AE-100-200-300-")
    assert payload["taskOrderDetail"] == [
        {"taskPath": "100,200"},
        {"taskPath": "300,400"},
    ]
