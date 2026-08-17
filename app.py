"""
Application factory — creates and configures FastAPI app.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from infrastructure.persistence.db import connect, disconnect
from infrastructure.persistence.camera_repository import camera_repository
from infrastructure.persistence.pairs_repository import pairs_repository
from infrastructure.persistence.node_repository import node_repository
from config.pairs import VALIDATE_PAIRS_BY_ZONE
from application.runtime.runtime_service import runtime_service
from application.container import container

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
        VALIDATE_PAIRS_BY_ZONE,
    )
    await runtime_service.start()
    yield
    # Shutdown
    runtime_service.stop()
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
    )

    app.include_router(cameras_router)
    app.include_router(state_router)
    app.include_router(runtime_router)
    app.include_router(nodes_router)
    app.include_router(pairs_router)

    return app