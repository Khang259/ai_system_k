"""FE-facing use cases for /api/v1."""
from application.fe_api.cameras import (
    CreateCamera,
    CreateRoi,
    DeleteCamera,
    DeleteRoi,
    GetCameras,
    GetRois,
    SetCameraStatus,
    UpdateCamera,
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
    GetSnapshotsByOrder,
    GetSystemActionLogs,
    GetUserActionLogs,
    MarkAllNotificationsRead,
    MarkNotificationRead,
)
from application.fe_api.nodes import (
    GetNodes,
    SetLock,
    SetMaintenance,
    Unlock,
    UpdateNode,
)
from application.fe_api.pairs import (
    CreatePairFe,
    DeletePairFe,
    GetNodePairs,
    SetPairEnabledFe,
    UpdatePairFe,
)
from application.fe_api.runtime_nodes import GetNodeRuntimeState
from application.fe_api.poll import GetPollSnapshot
from application.fe_api.zones import GetZones

__all__ = [
    "GetCameras",
    "GetRois",
    "SetCameraStatus",
    "CreateCamera",
    "UpdateCamera",
    "DeleteCamera",
    "CreateRoi",
    "UpdateRoi",
    "DeleteRoi",
    "GetNodes",
    "GetNodeRuntimeState",
    "GetPollSnapshot",
    "UpdateNode",
    "SetMaintenance",
    "SetLock",
    "Unlock",
    "GetZones",
    "GetNodePairs",
    "CreatePairFe",
    "UpdatePairFe",
    "DeletePairFe",
    "SetPairEnabledFe",
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
    "GetSnapshotsByOrder",
]
