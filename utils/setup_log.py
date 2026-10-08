import logging
from datetime import datetime
import os


def _resolve_level(level):
    """level=None → settings.LOG_LEVEL (default INFO). Có thể truyền int hoặc tên ('DEBUG')."""
    if level is not None:
        if isinstance(level, int):
            return level
        return getattr(logging, str(level).upper(), logging.INFO)
    try:
        from config.settings import settings

        name = (getattr(settings, "LOG_LEVEL", None) or "INFO").upper()
        return getattr(logging, name, logging.INFO)
    except Exception:
        return logging.INFO


def setup_logger(name, log_file, level=None):
    """Setup logger with file handler."""
    date_str = datetime.now().strftime("%Y%m%d")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    # encoding utf-8: log tiếng Việt có dấu + ký tự → sẽ lỗi trên console cp1252
    handler = logging.FileHandler(f"{log_file}_{date_str}.log", encoding="utf-8")
    handler.setFormatter(formatter)

    resolved = _resolve_level(level)
    logger = logging.getLogger(name)
    logger.setLevel(resolved)
    logger.addHandler(handler)

    return logger
