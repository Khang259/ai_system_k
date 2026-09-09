"""
Dọn file cũ định kỳ — hiện dùng cho logs, mở sẵn cho snapshot.

Chạy trong thread riêng theo cùng khuôn với MediaMtxRunner: threading.Event
làm cờ dừng để stop() thoát ngay, không phải chờ hết chu kỳ 24h.
"""
from __future__ import annotations

import os
import re
import threading
from datetime import date, datetime
from typing import Callable, List, Sequence, Tuple

from utils.setup_log import setup_logger

logger = setup_logger("retention", "logs/retention/log")

# Khớp đúng layout của utils.setup_log: logs/<tên logger>/log_YYYYMMDD.log
_LOG_NAME_RE = re.compile(r"^log_(\d{8})\.log$")

CleanupJob = Callable[[], None]


def purge_old_logs(logs_dir: str = "logs", keep_days: int = 5) -> Tuple[int, int]:
    """
    Xóa log cũ hơn keep_days, tính tuổi theo NGÀY TRONG TÊN FILE.

    Không dùng mtime: setup_log chốt tên file lúc import nên app chạy qua nửa
    đêm vẫn ghi tiếp vào file ngày cũ — mtime khi đó là hôm nay, không phản
    ánh ngày của log. Tên file mới là thứ nói đúng log thuộc ngày nào.

    Tuổi = số ngày từ ngày trong tên tới hôm nay; xóa khi tuổi >= keep_days.
    keep_days=5 giữ lại đúng 5 ngày gần nhất, kể cả hôm nay.

    File không khớp log_YYYYMMDD.log được bỏ qua — chỉ dọn thứ mình tạo ra.

    Returns: (số file đã xóa, số byte thu hồi)
    """
    if keep_days < 1:
        logger.warning(f"keep_days={keep_days} không hợp lệ, bỏ qua dọn log")
        return 0, 0

    if not os.path.isdir(logs_dir):
        return 0, 0

    today = date.today()
    removed = 0
    freed = 0
    locked: List[str] = []

    for dirpath, _dirnames, filenames in os.walk(logs_dir):
        for filename in filenames:
            match = _LOG_NAME_RE.match(filename)
            if match is None:
                continue

            try:
                file_date = datetime.strptime(match.group(1), "%Y%m%d").date()
            except ValueError:
                # Tên đúng dạng 8 số nhưng không phải ngày thật (vd 20261332)
                continue

            if (today - file_date).days < keep_days:
                continue

            path = os.path.join(dirpath, filename)
            try:
                size = os.path.getsize(path)
                os.remove(path)
                removed += 1
                freed += size
            except PermissionError:
                # Windows không cho xóa file đang có handle mở. Xảy ra khi app
                # chạy liên tục > keep_days ngày: FileHandler vẫn giữ file của
                # ngày khởi động. Bỏ qua, lần sau app restart sẽ dọn được.
                locked.append(path)
            except OSError as e:
                logger.warning(f"Không xóa được {path}: {e}")

    if removed:
        logger.info(
            f"Đã xóa {removed} file log cũ hơn {keep_days} ngày, "
            f"thu hồi {freed / 1024 / 1024:.2f} MB"
        )
    if locked:
        logger.info(
            f"{len(locked)} file log đang được ghi nên chưa xóa: "
            f"{', '.join(locked[:3])}"
        )

    return removed, freed


class RetentionRunner:
    """
    Chạy danh sách job dọn dẹp: một lượt lúc start, rồi mỗi interval_sec.

    Nhận list job thay vì gắn cứng vào log để thêm việc mới (vd
    SnapshotFsStore.cleanup_old_snapshots) chỉ là thêm một phần tử.
    """

    def __init__(self, jobs: Sequence[CleanupJob], interval_sec: float = 86400.0):
        self.jobs = list(jobs)
        self.interval_sec = float(interval_sec)

        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> None:
        """Gọi mọi job. Một job lỗi không được làm chết các job còn lại."""
        for job in self.jobs:
            try:
                job()
            except Exception as e:
                name = getattr(job, "__name__", repr(job))
                logger.error(f"Job dọn dẹp '{name}' lỗi: {e}")

    def start(self) -> None:
        if self.interval_sec <= 0:
            logger.info("Retention tắt (interval_sec <= 0)")
            return
        if not self.jobs:
            logger.info("Retention không có job nào, bỏ qua")
            return

        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="RetentionRunner"
        )
        self._thread.start()
        logger.info(
            f"Retention started ({len(self.jobs)} job, chạy mỗi "
            f"{self.interval_sec / 3600:.1f}h)"
        )

    def stop(self) -> None:
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
            logger.info("Retention stopped")

    def _loop(self) -> None:
        # Dọn ngay lúc khởi động: app thường restart dày hơn chu kỳ 24h
        self.run_once()
        while not self._stop_flag.wait(self.interval_sec):
            self.run_once()
