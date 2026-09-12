"""FE-facing use cases for /api/v1."""
from application.fe_api.cameras import (
    CreateRoi,
    DeleteRoi,
    GetCameras,
    GetRois,
    SetCameraStatus,
    UpdateRoi,
)
from application.fe_api.maps import (
    DownloadMapZip,
    GetCompress,
    ImportMap,
    ListMapVersions,
    SetActiveMap,
)
from application.fe_api.logs import (
    GetAuditLogs,
    GetNotifications,
    GetSnapshotImage,
    GetSystemActionLogs,
    GetUserActionLogs,
    MarkAllNotificationsRead,
    MarkNotificationRead,
)
from application.fe_api.nodes import GetNodes, SetLock, SetMaintenance, Unlock
from application.fe_api.pairs import GetNodePairs
from application.fe_api.zones import GetZones

__all__ = [
    "GetCameras",
    "GetRois",
    "SetCameraStatus",
    "CreateRoi",
    "UpdateRoi",
    "DeleteRoi",
    "GetNodes",
    "SetMaintenance",
    "SetLock",
    "Unlock",
    "GetZones",
    "GetNodePairs",
    "ImportMap",
    "ListMapVersions",
    "SetActiveMap",
    "GetCompress",
    "DownloadMapZip",
    "GetAuditLogs",
    "GetUserActionLogs",
    "GetSystemActionLogs",
    "GetNotifications",
    "MarkNotificationRead",
    "MarkAllNotificationsRead",
    "GetSnapshotImage",
]
