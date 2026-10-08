"""
Application factory — creates and configures FastAPI app.
"""
import asyncio
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import settings
from application.container import container
from application.runtime.runtime_service import runtime_service
from infrastructure.auth import (
    ActionAuditAdapter,
    AuthAuditAdapter,
    BcryptHasher,
    JwtTokenService,
    SystemActionAuditAdapter,
    ensure_auth_indexes,
)
from infrastructure.persistence import (
    MongoHealthAdapter,
    action_log_repository,
    audit_log_repository,
    camera_repository,
    connect,
    disconnect,
    dispatch_log_repository,
    map_state_repository,
    map_version_repository,
    node_repository,
    notification_repository,
    pairs_repository,
    refresh_token_repository,
    snapshot_repository,
    user_repository,
    zone_repository,
)
from infrastructure.ics import HttpOrderQuery
from infrastructure.storage import MapZipStore, RetentionRunner, purge_old_logs
from infrastructure.webrtc import MediaMtxGateway, MediaMtxRunner
from utils.setup_log import setup_logger

from presentation.openapi_responses import AUTH
from presentation.routes.v1 import (
    auth_router,
    cameras_v1_router,
    dispatch_v1_router,
    external_server_v1_router,
    logs_v1_router,
    maps_v1_router,
    nodes_v1_router,
    notifications_v1_router,
    pairs_v1_router,
    poll_v1_router,
    runtime_v1_router,
    sandbox_v1_router,
    snapshots_v1_router,
    system_v1_router,
    zones_v1_router,
)

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
    container.bind_ics_order_query(HttpOrderQuery(settings.ICS_ORDER_LIST_URL))

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
    container.bind_system_action_audit(SystemActionAuditAdapter())
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
    from application.cameras import ice_servers_for_mediamtx

    container.webrtc_gateway.apply_ice_servers(ice_servers_for_mediamtx())

    # Bind trước khi start: nếu start lỗi thì /api/v1/runtime/reload vẫn gọi được
    container.bind_runtime_control(runtime_service)
    try:
        await runtime_service.start()
    except Exception as e:
        # GPU / model / camera lỗi không được làm sập cả app — nhóm CRUD và
        # auth không cần runtime. Container giữ Null ports nên các use case
        # runtime trả "not ready" thay vì nổ; GET /api/v1/system/get_health
        # trả 503 degraded. Sửa xong gọi POST /api/v1/runtime/reload.
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

        Áp cho cả app: lỗi framework (404/405) và HTTPException `/api/v1` đi qua đây.
        """
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(cameras_v1_router, prefix="/api/v1/cameras", tags=["cameras-v1"], responses=AUTH)
    app.include_router(zones_v1_router, prefix="/api/v1/zones", tags=["zones-v1"], responses=AUTH)
    app.include_router(system_v1_router, prefix="/api/v1/system", tags=["system-v1"], responses=AUTH)
    app.include_router(runtime_v1_router, prefix="/api/v1/runtime", tags=["runtime-v1"], responses=AUTH)
    app.include_router(nodes_v1_router, prefix="/api/v1/nodes", tags=["nodes-v1"], responses=AUTH)
    app.include_router(pairs_v1_router, prefix="/api/v1/pairs", tags=["pairs-v1"], responses=AUTH)
    app.include_router(logs_v1_router, prefix="/api/v1/logs", tags=["logs-v1"], responses=AUTH)
    app.include_router(notifications_v1_router, prefix="/api/v1/notifications", tags=["notifications-v1"], responses=AUTH)
    app.include_router(snapshots_v1_router, prefix="/api/v1/snapshots", tags=["snapshots-v1"], responses=AUTH)
    app.include_router(maps_v1_router, prefix="/api/v1/maps", tags=["maps-v1"], responses=AUTH)
    app.include_router(poll_v1_router, prefix="/api/v1/poll", tags=["poll-v1"], responses=AUTH)
    app.include_router(dispatch_v1_router, prefix="/api/v1/dispatch", tags=["dispatch-v1"], responses=AUTH)
    # Webhook external — không Bearer nên không gắn responses=AUTH
    app.include_router(external_server_v1_router, prefix="/api/v1/external_server", tags=["external-server-v1"])
    if settings.RUNTIME_MODE == "sandbox":
        app.include_router(sandbox_v1_router, prefix="/api/v1/sandbox", tags=["sandbox-v1"], responses=AUTH)

    return app