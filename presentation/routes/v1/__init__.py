from presentation.routes.v1.auth import router as auth_router
from presentation.routes.v1.cameras import router as cameras_v1_router
from presentation.routes.v1.dispatch import router as dispatch_v1_router
from presentation.routes.v1.logs import router as logs_v1_router
from presentation.routes.v1.maps import router as maps_v1_router
from presentation.routes.v1.nodes import router as nodes_v1_router
from presentation.routes.v1.notifications import router as notifications_v1_router
from presentation.routes.v1.poll import router as poll_v1_router
from presentation.routes.v1.snapshots import router as snapshots_v1_router
from presentation.routes.v1.system import router as system_v1_router
from presentation.routes.v1.zones import router as zones_v1_router

__all__ = [
    "auth_router",
    "cameras_v1_router",
    "zones_v1_router",
    "system_v1_router",
    "nodes_v1_router",
    "dispatch_v1_router",
    "logs_v1_router",
    "notifications_v1_router",
    "snapshots_v1_router",
    "maps_v1_router",
    "poll_v1_router",
]
