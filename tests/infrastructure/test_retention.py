"""
Dọn log cũ + RetentionRunner.

Tuổi file tính theo ngày trong tên (log_YYYYMMDD.log), không theo mtime — nên
test dựng tên file lệch ngày so với hôm nay thay vì phải giả lập mtime.
"""
from __future__ import annotations

from datetime import date, timedelta

from infrastructure.storage.retention import RetentionRunner, purge_old_logs


def _make_log(logs_dir, subdir: str, days_ago: int):
    """Tạo logs_dir/<subdir>/log_<ngày cách đây days_ago>.log, trả về Path"""
    day = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
    folder = logs_dir / subdir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"log_{day}.log"
    path.write_text("x" * 100, encoding="utf-8")
    return path


def test_purges_files_older_than_keep_days(tmp_path):
    logs = tmp_path / "logs"
    today = _make_log(logs, "dispatch", 0)
    edge_keep = _make_log(logs, "dispatch", 4)   # tuổi 4 < 5 → giữ
    edge_drop = _make_log(logs, "dispatch", 5)   # tuổi 5 >= 5 → xóa
    old = _make_log(logs, "camera_processor", 30)

    removed, freed = purge_old_logs(str(logs), keep_days=5)

    assert removed == 2
    assert freed == 200
    assert today.is_file()
    assert edge_keep.is_file()
    assert not edge_drop.exists()
    assert not old.exists()


def test_ignores_files_not_matching_log_pattern(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    others = [logs / "notes.txt", logs / "log_2026.log", logs / "trace.json"]
    for path in others:
        path.write_text("keep me", encoding="utf-8")

    removed, _ = purge_old_logs(str(logs), keep_days=1)

    assert removed == 0
    assert all(path.is_file() for path in others)


def test_ignores_eight_digits_that_are_not_a_real_date(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    bogus = logs / "log_20261332.log"  # tháng 13, ngày 32
    bogus.write_text("x", encoding="utf-8")

    removed, _ = purge_old_logs(str(logs), keep_days=1)

    assert removed == 0
    assert bogus.is_file()


def test_locked_file_does_not_raise(tmp_path, monkeypatch):
    """Windows chặn xóa file đang mở — phải bỏ qua, không làm chết scheduler."""
    logs = tmp_path / "logs"
    stale = _make_log(logs, "dispatch", 10)

    def deny(_path):
        raise PermissionError(32, "file đang được tiến trình khác dùng")

    monkeypatch.setattr("infrastructure.storage.retention.os.remove", deny)

    removed, freed = purge_old_logs(str(logs), keep_days=5)

    assert (removed, freed) == (0, 0)
    assert stale.is_file()


def test_missing_dir_and_bad_keep_days_are_noop(tmp_path):
    assert purge_old_logs(str(tmp_path / "khong-ton-tai"), keep_days=5) == (0, 0)

    logs = tmp_path / "logs"
    stale = _make_log(logs, "dispatch", 99)
    assert purge_old_logs(str(logs), keep_days=0) == (0, 0)
    assert stale.is_file()


def test_run_once_runs_every_job_even_if_one_fails():
    calls = []

    def boom():
        calls.append("boom")
        raise RuntimeError("job lỗi")

    RetentionRunner(
        [boom, lambda: calls.append("second")], interval_sec=3600
    ).run_once()

    assert calls == ["boom", "second"]


def test_start_cleans_immediately_then_stop_joins():
    calls = []
    runner = RetentionRunner([lambda: calls.append(1)], interval_sec=3600)

    runner.start()
    runner.stop()

    assert calls == [1]


def test_disabled_when_interval_not_positive():
    calls = []
    runner = RetentionRunner([lambda: calls.append(1)], interval_sec=0)

    runner.start()
    runner.stop()

    assert calls == []
