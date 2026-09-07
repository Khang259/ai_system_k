"""
Application factory — creates and configures FastAPI app.
"""
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from infrastructure.persistence.db import connect, disconnect
from infrastructure.persistence.camera_repository import camera_repository
from infrastructure.persistence.pairs_repository import pairs_repository
from infrastructure.persistence.node_repository import node_repository
from application.runtime.runtime_service import runtime_service
from application.container import container
from infrastructure.webrtc import MediaMtxGateway
from infrastructure.webrtc.mediamtx_runner import start_mediamtx, stop_mediamtx

from presentation.routes.cameras import router as cameras_router
from presentation.routes.state   import router as state_router
from presentation.routes.runtime import router as runtime_router
from presentation.routes.nodes   import router as nodes_router
from presentation.routes.pairs   import router as pairs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect(settings.MONGODB_URL, settings.MONGODB_DB)
    container.bind_repos(
        camera_repository,
        pairs_repository,
        node_repository,
    )
    start_mediamtx(
        settings.MEDIAMTX_BIN,
        settings.MEDIAMTX_YML,
        api_url=settings.MEDIAMTX_API_URL,
    )
    container.bind_webrtc(
        MediaMtxGateway(settings.MEDIAMTX_API_URL, settings.MEDIAMTX_WEBRTC_URL)
    )
    from application.cameras.webrtc_ice import ice_servers_for_mediamtx

    container.webrtc_gateway.apply_ice_servers(ice_servers_for_mediamtx())
    await runtime_service.start()
    yield
    # Shutdown
    runtime_service.stop()
    stop_mediamtx()
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

    app.include_router(cameras_router)
    app.include_router(state_router)
    app.include_router(runtime_router)
    app.include_router(nodes_router)
    app.include_router(pairs_router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app