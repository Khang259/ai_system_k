"""
Centralized configuration — loaded from .env via pydantic-settings.
Replaces both settings.py and config.py in the original codebase.

State-machine timers: SSOT runtime. Default lấy từ domain.settings;
đổi lúc chạy qua .env. RuntimeService inject vào NodeState.
"""
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import domain.settings as domain_defaults


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
    ICS_PROCESS_SINGLE: str = "SingleGroupAE5"
    ICS_PROCESS_EMPTY: str  = "SEGroupAE"
    ICS_PROCESS_DOUBLE: str = "DoubleGroupAE"

    # ── AI Inference ──────────────────────────────────────────
    MODEL_PATH: str              = "models/model_test.engine"
    MODEL_HEIGHT: int            = 480  # engine H — phải khớp imgsz export
    MODEL_WIDTH: int             = 640  # engine W
    THRESHOLD_DETECT: float      = 0.4  # NMS + ROI detect: loại bỏ detection confidence thấp
    THRESHOLD_COVERAGE: float    = 0.5
    INFERENCE_MAX_QUEUE_SIZE: int  = 500
    INFERENCE_MIN_BATCH_SIZE: int  = 1   # TRT profile min — 1 camera / dev
    INFERENCE_OPT_BATCH_SIZE: int  = 8   # TRT profile opt
    INFERENCE_MAX_BATCH_SIZE: int  = 32  # TRT profile max — prod
    INFERENCE_BATCH_TIMEOUT: float = 0.3
    INFERENCE_NUM_STREAMS: int     = 2   # D: N TRT context (mỗi cái 1 stream + I/O). <1.15x → đặt 1
    DECODE_STREAM_POOL_SIZE: int   = 8   # C: pool decode, round-robin camera
    INFERENCE_USE_PREALLOCATED_QUEUE: bool = True  # Use pre-allocated ring buffer queue
    START_WAIT_MODEL_SEC: float    = 30.0  # start-all chờ model load
    START_WAIT_STREAM_SEC: float   = 45.0  # start-all chờ ≥1 camera có frame
    DECODE_WAIT_FIRST_FRAME_SEC: float = 30.0  # NVDEC chờ frame đầu tiên

    # ── Snapshot ──────────────────────────────────────────────
    ENABLE_SNAPSHOTS: bool  = False
    SNAPSHOT_DIR: str       = "snapshots"
    SNAPSHOT_QUALITY: int   = 85   # JPEG quality — reduced from 95 to save disk

    # ── Map zip (global versions) ─────────────────────────────
    MAP_STORAGE_DIR: str      = "data/maps"
    MAP_VERSION_KEEP: int     = 5     # giữ tối đa N bản; import vượt → xoá bản cũ nhất
    MAP_MAX_UPLOAD_MB: int    = 100

    # ── Auth (short session + refresh token) ──────────────────
    # Để trống = sinh secret ngẫu nhiên mỗi lần khởi động → token cũ mất hiệu
    # lực sau restart. Tiện cho dev, PHẢI set trong .env cho production.
    JWT_SECRET: str            = ""
    JWT_ALGORITHM: str         = "HS256"
    ACCESS_TOKEN_TTL_MIN: int  = 15   # ngắn: không revoke được nên đừng để dài
    REFRESH_TOKEN_TTL_DAYS: int = 7
    LOGIN_MAX_FAILED: int      = 10    # số lần sai liên tiếp trước khi khoá
    LOGIN_LOCKOUT_MIN: int     = 5   # cửa sổ đếm số lần sai; 0 = tắt rate limit

    # ── Log retention ─────────────────────────────────────────
    LOG_KEEP_DAYS: int              = 5        # giữ N ngày gần nhất, kể cả hôm nay
    LOG_CLEANUP_INTERVAL_SEC: float = 86400.0  # chu kỳ dọn; 0 = tắt

    # ── Preview JPEG (Swagger / bước 1; WebRTC sau) ───────────
    PREVIEW_JPEG_QUALITY: int    = 80
    PREVIEW_INTERVAL_SEC: float  = 0.2   # encode tối đa ~5 fps khi đang watch
    PREVIEW_WATCH_SEC: float     = 15.0  # GET gia hạn watch
    PREVIEW_WAIT_SEC: float      = 2.0   # GET chờ frame đầu
    WEBRTC_MAX_SESSIONS: int     = 4     # F3: grid 2×2
    WEBRTC_STUN_URL: str         = ""    # F7: trống = LAN; vd stun:stun.l.google.com:19302
    WEBRTC_TURN_URL: str         = ""    # F7: trống = không TURN
    WEBRTC_TURN_USER: str        = ""
    WEBRTC_TURN_PASS: str        = ""
    MEDIAMTX_BIN: str            = ""    # trống: which + bin/mediamtx.exe
    MEDIAMTX_YML: str            = "config/mediamtx.yml"
    MEDIAMTX_API_URL: str        = "http://127.0.0.1:9997"
    MEDIAMTX_WEBRTC_URL: str     = "http://127.0.0.1:8890"
    MEDIAMTX_WATCHDOG_SEC: float = 10.0  # chu kỳ probe API; 0 = tắt watchdog
    MEDIAMTX_MAX_RESTARTS: int   = 5     # restart liên tiếp tối đa trước khi bỏ cuộc

    # ── State Machine Timers (SSOT runtime; default = domain.settings) ─
    START_READY_AFTER_SEC: int = domain_defaults.START_READY_AFTER_SEC
    END_READY_AFTER_SEC: int = domain_defaults.END_READY_AFTER_SEC
    END_FLAG_RESET_AFTER_SEC: int = domain_defaults.END_FLAG_RESET_AFTER_SEC
    ENABLE_TORCH_PROFILER: bool  = False # PyTorch Profiler — ghi trace.json sau N batches
    EMPTY_DEADLINE_SEC: int     = 15   # chờ ghép double tối đa 15s trước khi gửi empty

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
