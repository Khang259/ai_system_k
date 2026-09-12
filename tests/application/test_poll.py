"""Poll snapshot use case."""
from __future__ import annotations

import asyncio

from application.fe_api.poll import GetPollSnapshot, compute_etag
from application.null_ports import NullMapStateStore, NullNotificationStore
from application.result import UseCaseResult


def _run(coro):
    return asyncio.run(coro)


class _Cam:
    async def execute(self):
        return UseCaseResult.ok(
            items=[
                {
                    "cameraId": 1,
                    "status": "streaming",
                    "enabled": True,
                    "zone": "AE5",
                    "error": None,
                }
            ]
        )


class _Zones:
    async def execute(self):
        return UseCaseResult.ok(
            items=[
                {
                    "id": "AE5",
                    "isRunning": True,
                    "isConfigEnabled": True,
                    "cameraCount": 1,
                    "nodeCount": 2,
                }
            ]
        )


def test_poll_snapshot_shape_and_stable_etag():
    notif = NullNotificationStore()
    state = NullMapStateStore()
    state.active = "v1"
    uc = GetPollSnapshot(_Cam(), _Zones(), notif, state, recommended_interval_sec=3)

    a = _run(uc.execute("u-1"))
    b = _run(uc.execute("u-1"))
    assert a.success
    assert a.data["pollIntervalSec"] == 3
    assert a.data["cameras"]["items"][0]["status"] == "streaming"
    assert a.data["zones"]["items"][0]["isRunning"] is True
    assert a.data["notifications"]["unreadCount"] == 0
    assert a.data["map"]["activeVersionId"] == "v1"
    assert a.data["etag"] == b.data["etag"]
    assert a.data["serverTime"] != ""  # may equal if same second — etag ignores it


def test_poll_include_subset():
    uc = GetPollSnapshot(
        _Cam(), _Zones(), NullNotificationStore(), NullMapStateStore()
    )
    r = _run(uc.execute("u-1", include={"notifications"}))
    assert "notifications" in r.data
    assert "cameras" not in r.data
    assert "zones" not in r.data


def test_compute_etag_stable():
    assert compute_etag({"a": 1}) == compute_etag({"a": 1})
    assert compute_etag({"a": 1}) != compute_etag({"a": 2})
