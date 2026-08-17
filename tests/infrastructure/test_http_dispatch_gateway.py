"""HttpDispatchGateway — mock requests, không ICS server thật."""
from unittest.mock import MagicMock, patch

from infrastructure.ics.http_dispatch_gateway import HttpDispatchGateway


def _response(status: int, code: int):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"code": code}
    return resp


def test_send_success_first_attempt():
    gw = HttpDispatchGateway("http://ics.test/add", retry=3, delay=0)
    with patch(
        "infrastructure.ics.http_dispatch_gateway.requests.post",
        return_value=_response(200, 1000),
    ) as post, patch("infrastructure.ics.http_dispatch_gateway.time.sleep"):
        assert gw.send({"orderId": "S-1"}) is True
        assert post.call_count == 1


def test_send_retries_then_success():
    gw = HttpDispatchGateway("http://ics.test/add", retry=3, delay=0)
    fail = _response(500, 0)
    ok = _response(200, 1000)
    with patch(
        "infrastructure.ics.http_dispatch_gateway.requests.post",
        side_effect=[fail, fail, ok],
    ) as post, patch("infrastructure.ics.http_dispatch_gateway.time.sleep") as sleep:
        assert gw.send({"orderId": "S-1"}) is True
        assert post.call_count == 3
        assert sleep.call_count == 2


def test_send_all_retries_fail():
    gw = HttpDispatchGateway("http://ics.test/add", retry=2, delay=0)
    with patch(
        "infrastructure.ics.http_dispatch_gateway.requests.post",
        side_effect=Exception("timeout"),
    ) as post, patch("infrastructure.ics.http_dispatch_gateway.time.sleep"):
        assert gw.send({"orderId": "S-1"}) is False
        assert post.call_count == 2


def test_send_rejects_non_1000_code():
    gw = HttpDispatchGateway("http://ics.test/add", retry=1, delay=0)
    with patch(
        "infrastructure.ics.http_dispatch_gateway.requests.post",
        return_value=_response(200, 999),
    ), patch("infrastructure.ics.http_dispatch_gateway.time.sleep"):
        assert gw.send({"orderId": "S-1"}) is False
