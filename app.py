"""
Application factory — creates and configures FastAPI app.
"""
import asyncio
from contextlib import asynccontextmanager
from functools import partial

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import settings
from infrastructure.persistence.db import connect, disconnect
from infrastructure.persistence.camera_repository import camera_repository
from infrastructure.persistence.pairs_repository import pairs_repository
from infrastructure.persistence.node_repository import node_repository
from application.runtime.runtime_service import runtime_service
from application.container import container
from infrastructure.webrtc import MediaMtxGateway
from infrastructure.webrtc.mediamtx_runner import MediaMtxRunner
from infrastructure.persistence.db_health import MongoHealthAdapter
from infrastructure.persistence.user_repository import user_repository
from infrastructure.persistence.refresh_token_repository import refresh_token_repository
from infrastructure.persistence.zone_repository import zone_repository
from infrastructure.persistence.log_repositories import (
    action_log_repository,
    audit_log_repository,
)
from infrastructure.persistence.dispatch_log_repository import dispatch_log_repository
from infrastructure.persistence.notification_repository import notification_repository
from infrastructure.persistence.snapshot_repository import snapshot_repository
from infrastructure.persistence.map_repository import (
    map_state_repository,
    map_version_repository,
)
from infrastructure.storage.map_zip_store import MapZipStore
from infrastructure.auth import (
    AuthAuditAdapter,
    BcryptHasher,
    JwtTokenService,
    ensure_auth_indexes,
)
from infrastructure.auth.action_audit_adapter import ActionAuditAdapter
from infrastructure.storage.retention import RetentionRunner, purge_old_logs
from utils.setup_log import setup_logger

from presentation.routes.v1 import (
    auth_router,
    cameras_v1_router,
    dispatch_v1_router,
    logs_v1_router,
    maps_v1_router,
    nodes_v1_router,
    notifications_v1_router,
    poll_v1_router,
    snapshots_v1_router,
    system_v1_router,
    zones_v1_router,
)
from presentation.routes.cameras import router as cameras_router
from presentation.routes.state   import router as state_router
from presentation.routes.runtime import router as runtime_router
from presentation.routes.nodes   import router as nodes_router
from presentation.routes.pairs   import router as pairs_router

logger = setup_logger("app", "logs/app/log")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect(settings.MONGODB_URL, settings.MONGODB_DB)
    container.bind_repos(
        camera_repository,
        pairs_repository,
        node_repository,
        zone_repository,
    )
    container.bind_db_health(MongoHealthAdapter())

    await ensure_auth_indexes()
    container.bind_auth(
        user_repository,
        refresh_token_repository,
        AuthAuditAdapter(),
        BcryptHasher(),
        JwtTokenService(
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
            access_ttl_min=settings.ACCESS_TOKEN_TTL_MIN,
            refresh_ttl_days=settings.REFRESH_TOKEN_TTL_DAYS,
        ),
    )
    container.bind_action_audit(ActionAuditAdapter())
    container.bind_log_stores(
        audit_log_repository,
        action_log_repository,
        dispatch_log_repository,
        notification_repository,
    )
    container.bind_snapshot_indexer(snapshot_repository)
    container.bind_node_lock_sync(node_repository)
    container.bind_event_loop(asyncio.get_running_loop())
    container.bind_map(
        map_version_repository,
        map_state_repository,
        MapZipStore(settings.MAP_STORAGE_DIR),
    )

    retention = RetentionRunner(
        [partial(purge_old_logs, keep_days=settings.LOG_KEEP_DAYS)],
        interval_sec=settings.LOG_CLEANUP_INTERVAL_SEC,
    )
    retention.start()

    mediamtx = MediaMtxRunner(
        settings.MEDIAMTX_BIN,
        settings.MEDIAMTX_YML,
        api_url=settings.MEDIAMTX_API_URL,
        watchdog_sec=settings.MEDIAMTX_WATCHDOG_SEC,
        max_restarts=settings.MEDIAMTX_MAX_RESTARTS,
    )
    mediamtx.start()
    container.bind_webrtc(
        MediaMtxGateway(settings.MEDIAMTX_API_URL, settings.MEDIAMTX_WEBRTC_URL),
        runner=mediamtx,
    )
    from application.cameras.webrtc_ice import ice_servers_for_mediamtx

    container.webrtc_gateway.apply_ice_servers(ice_servers_for_mediamtx())

    # Bind trước khi start: nếu start lỗi thì /runtime/reload vẫn gọi được
    container.bind_runtime_control(runtime_service)
    try:
        await runtime_service.start()
    except Exception as e:
        # GPU / model / camera lỗi không được làm sập cả app — nhóm CRUD và
        # auth không cần runtime. Container giữ Null ports nên các use case
        # runtime trả "not ready" thay vì nổ, `/health` trả 503 degraded.
        # Sửa xong gọi POST /runtime/reload, không cần restart.
        logger.error(f"Runtime không khởi động được, API chạy degraded: {e}", exc_info=True)

    yield
    # Shutdown
    runtime_service.stop()
    mediamtx.stop()
    retention.stop()
    await disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AMR Camera Dispatch System",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Location"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_as_message(request, exc: StarletteHTTPException):
        """
        FE mong lỗi dạng `{"message": ...}`, còn FastAPI trả `{"detail": ...}`.

        Áp cho cả app: route cũ tự tạo JSONResponse nên không bị ảnh hưởng, chỉ
        lỗi do framework sinh (404/405) và HTTPException của nhóm /api/v1 đi qua đây.
        """
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(auth_router)
    app.include_router(cameras_v1_router)
    app.include_router(zones_v1_router)
    app.include_router(system_v1_router)
    app.include_router(nodes_v1_router)
    app.include_router(dispatch_v1_router)
    app.include_router(logs_v1_router)
    app.include_router(notifications_v1_router)
    app.include_router(snapshots_v1_router)
    app.include_router(maps_v1_router)
    app.include_router(poll_v1_router)
    app.include_router(cameras_router)
    app.include_router(state_router)
    app.include_router(runtime_router)
    app.include_router(nodes_router)
    app.include_router(pairs_router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app