"""Camera + ROI use cases cho /api/v1 (re-export — tách file theo nhóm)."""
from application.fe_api.cameras_crud import CreateCamera, DeleteCamera
from application.fe_api.cameras_read import GetCameras, GetRois
from application.fe_api.cameras_status import SetCameraStatus
from application.fe_api.cameras_update import UpdateCamera
from application.fe_api.rois import CreateRoi, DeleteRoi, UpdateRoi

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
]
