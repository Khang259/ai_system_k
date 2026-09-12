"""Đợt 4 — logs, notifications, snapshot file, find_page serialize."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from application.fe_api.log_mappers import map_audit, map_dispatch, parse_device
from application.fe_api.logs import (
    GetAuditLogs,
    GetNotifications,
    GetSnapshotImage,
    GetSystemActionLogs,
    GetUserActionLogs,
    MarkAllNotificationsRead,
    MarkNotificationRead,
)
from infrastructure.persistence.base_repository import _serialize


def _run(coro):
    return asyncio.run(coro)


class FakePaged:
    def __init__(self, docs):
        self.docs = docs

    async def find_page(self, query, page=1, page_size=20, sort=None):
        return list(self.docs), len(self.docs)


class FakeNotif:
    def __init__(self):
        self.rows = [
            {
                "id": "n1",
                "title": "Dispatch fail",
                "message": "order x",
                "type": "dispatch.failed",
                "created_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                "read_at": None,
                "meta": {},
                "snapshot_file": "order1.jpg",
            }
        ]

    async def list_for_user(self, user_id, *, unread_only=False, page=1, page_size=20):
        rows = self.rows
        if unread_only:
            rows = [r for r in rows if r["read_at"] is None]
        return rows, len(rows)

    async def mark_read(self, notification_id, user_id):
        for r in self.rows:
            if r["id"] == notification_id:
                r["read_at"] = datetime.now(timezone.utc)
                return True
        return False

    async def mark_all_read(self, user_id):
        n = 0
        for r in self.rows:
            if r["read_at"] is None:
                r["read_at"] = datetime.now(timezone.utc)
                n += 1
        return n


def test_serialize_id():
    assert _serialize({"_id": "abc", "user": "u"}) == {"id": "abc", "user": "u"}


def test_parse_device():
    assert "Chrome" in parse_device(
        "Mozilla/5.0 (Windows NT 10.0) Chrome/141.0.0.0 Safari/537.36"
    )


def test_get_audit_logs_shape():
    store = FakePaged(
        [
            {
                "id": "a1",
                "user": "admin",
                "role": "admin",
                "event": "login_success",
                "ip": "1.1.1.1",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/141.0",
                "created_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
            }
        ]
    )
    result = _run(GetAuditLogs(store).execute(page=1, page_size=20))
    assert result.success
    item = result.data["items"][0]
    assert item["userName"] == "admin"
    assert item["action"] == "login_success"
    assert item["ipAddress"] == "1.1.1.1"
    assert result.data["pageSize"] == 20


def test_map_dispatch_duration_ms():
    mapped = map_dispatch(
        {
            "id": "d1",
            "order_id": "o1",
            "status": "success",
            "duration_sec": 2.5,
            "start_point": "start_1",
            "end_point": "end_1",
            "dispatched_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
        }
    )
    assert mapped["durationMs"] == 2500
    assert mapped["result"] == "success"


def test_user_and_system_logs():
    actions = FakePaged(
        [
            {
                "id": "u1",
                "user": "op",
                "role": "operator",
                "action": "create_roi",
                "endpoint": "/api/v1/cameras/create_roi",
                "ip": "127.0.0.1",
                "status": 200,
                "source": "user",
                "payload": {"cameraId": 1},
                "created_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
            }
        ]
    )
    user = _run(GetUserActionLogs(actions).execute())
    assert user.data["items"][0]["action"] == "create_roi"

    dispatch = FakePaged(
        [{"id": "d1", "order_id": "o1", "status": "failed", "error_msg": "timeout"}]
    )
    system = _run(GetSystemActionLogs(dispatch).execute())
    assert system.data["items"][0]["errorMessage"] == "timeout"


def test_notifications_and_mark():
    store = FakeNotif()
    listed = _run(GetNotifications(store).execute("u-1"))
    assert listed.data["items"][0]["snapshotImageUrl"].endswith("file=order1.jpg")

    ok = _run(MarkNotificationRead(store).execute("n1", "u-1"))
    assert ok.success
    all_read = _run(MarkAllNotificationsRead(store).execute("u-1"))
    assert all_read.data["updated"] == 0


def test_snapshot_image_safe_path(tmp_path):
    img = tmp_path / "pair.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    uc = GetSnapshotImage(str(tmp_path))
    ok = uc.execute("pair.jpg")
    assert ok.success
    assert ok.data["jpeg"].startswith(b"\xff\xd8")

    bad = uc.execute("../secret.jpg")
    assert not bad.success
    missing = uc.execute("gone.jpg")
    assert missing.data["http_status"] == 404
