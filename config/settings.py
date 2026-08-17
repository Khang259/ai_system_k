"""
Centralized configuration — loaded from .env via pydantic-settings.
Replaces both settings.py and config.py in the original codebase.
"""
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Server ────────────────────────────────────────────────
    API_SERVER_HOST: str = "0.0.0.0"
    API_SERVER_PORT: int = 5000
    API_LOG_LEVEL: str   = "info"

    # ── MongoDB ───────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://127.0.0.1:27018"
    MONGODB_DB: str = "db_kortek"

    # ── AMR / ICS ─────────────────────────────────────────────
    ICS_URL: str          = "http://192.168.1.30:7000/ics/taskOrder/addTask"
    END_POINT_EMPTY: str  = "end_10001546"
    ICS_RETRY_TIMES: int  = 3
    ICS_RETRY_DELAY: float = 1.0  # seconds between retries

    # ── AI Inference ──────────────────────────────────────────
    MODEL_PATH: str              = "models/model_test.engine"
    THRESHOLD_DETECT: float      = 0.4
    THRESHOLD_COVERAGE: float    = 0.5
    INFERENCE_MAX_QUEUE_SIZE: int  = 500
    INFERENCE_MAX_BATCH_SIZE: int  = 32
    INFERENCE_BATCH_TIMEOUT: float = 1.0
    INFERENCE_NUM_STREAMS: int     = 3
    USE_GPU_DECODE: bool           = True
    START_WAIT_MODEL_SEC: float    = 30.0  # start-all chờ model load
    START_WAIT_STREAM_SEC: float   = 15.0  # start-all chờ ≥1 camera có frame

    # ── Snapshot ──────────────────────────────────────────────
    ENABLE_SNAPSHOTS: bool  = False
    SNAPSHOT_DIR: str       = "snapshots"
    SNAPSHOT_QUALITY: int   = 85   # JPEG quality — reduced from 95 to save disk

    # ── State Machine Timers (override domain.settings defaults) ─
    START_READY_AFTER_SEC: int  = 30   # start node phải giữ state=True ít nhất 30s
    END_READY_AFTER_SEC: int    = 60   # end node phải giữ state=False ít nhất 60s
    END_FLAG_RESET_AFTER_SEC: int = 30  # end có hàng lại khi đang flag → reset pair
    EMPTY_DEADLINE_SEC: int     = 15   # chờ ghép double tối đa 15s trước khi gửi empty

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
