"""Composition root — wire ports into use cases. Singleton module-level `container`."""
from __future__ import annotations

from application.scan_session import ScanSession
from application.null_ports import (
    NullCameraConfigRepo,
    NullCameraRuntime,
    NullDispatchGateway,
    NullInference,
    NullNodeRepo,
    NullNodeStateStore,
    NullPairsRepo,
    NullRuntimeControl,
    NullZonePairs,
)
from application.state.update_detection import UpdateDetection
from application.state.toggle_flag import ToggleFlag
from application.state.reset_flags import ResetFlagsByOrder
from application.state.get_all_points import GetAllPoints
from application.state.get_zone_state import GetZoneState
from application.cameras.start_stop import StartAllCameras, StopAllCameras
from application.cameras.zone import StartZoneCameras, StopZoneCameras
from application.cameras.get_status import GetCameraStatus
from application.cameras.confirm_ready import ConfirmReady
from application.cameras.pause_scan import PauseScan
from application.cameras.on_dispatch_success import OnDispatchSuccess
from application.cameras_config.crud import (
    ListCameraConfigs,
    ListCameraConfigsByArea,
    CreateCameraConfig,
    UpdateCameraConfig,
    DeleteCameraConfig,
)
from application.nodes.crud import (
    GetNodesByZone,
    GetNodeById,
    SetNodeEnabled,
    UpdateNodePriority,
    CreateNode,
    DeleteNode,
)
from application.nodes.camera_nodes import DisableCameraNodes, EnableCameraNodes
from application.pairs.crud import GetPairsByZone, SetPairEnabled, CreatePair, DeletePair
from application.runtime.control import StartRuntime, StopRuntime, GetRuntimeStatus, ReloadRuntime
from application.dispatch.run_cycle import RunDispatchCycle


class AppContainer:
    def __init__(self) -> None:
        self.scan_session = ScanSession()
        self.cameras = NullCameraRuntime()
        self.inference = NullInference()
        self.state = NullNodeStateStore()
        self.camera_configs = NullCameraConfigRepo()
        self.pairs_repo = NullPairsRepo()
        self.nodes_repo = NullNodeRepo()
        self.runtime_control = NullRuntimeControl()
        self.zone_pairs = NullZonePairs()
        self.dispatch_gateway = NullDispatchGateway()
        self._wire()

    def bind_repos(self, camera_repo, pairs_repo, node_repo, zone_pairs) -> None:
        from infrastructure.adapters import ZonePairsAdapter

        self.camera_configs = camera_repo
        self.pairs_repo = pairs_repo
        self.nodes_repo = node_repo
        self.zone_pairs = ZonePairsAdapter(zone_pairs)
        self._wire()

    def bind_dispatch_gateway(self, gateway) -> None:
        self.dispatch_gateway = gateway
        self._wire()

    def bind_runtime(self, camera_manager, inference_engine, state_manager, runtime_control) -> None:
        from infrastructure.adapters import (
            CameraRuntimeAdapter,
            InferenceAdapter,
            NodeStateAdapter,
        )

        self.cameras = CameraRuntimeAdapter(camera_manager)
        self.inference = InferenceAdapter(inference_engine)
        self.state = NodeStateAdapter(state_manager)
        self.runtime_control = runtime_control
        self._wire()

    def unbind_runtime(self) -> None:
        self.scan_session.reset()
        self.cameras = NullCameraRuntime()
        self.inference = NullInference()
        self.state = NullNodeStateStore()
        self._wire()

    def _wire(self) -> None:
        scan = self.scan_session
        cams = self.cameras
        inf = self.inference
        state = self.state

        self.update_detection = UpdateDetection(state)
        self.toggle_flag = ToggleFlag(state)
        self.reset_flags = ResetFlagsByOrder(state)
        self.get_all_points = GetAllPoints(state)
        self.get_zone_state = GetZoneState(state, self.zone_pairs)

        from config.settings import settings

        self.start_all_cameras = StartAllCameras(
            cams,
            inf,
            wait_model_sec=settings.START_WAIT_MODEL_SEC,
            wait_stream_sec=settings.START_WAIT_STREAM_SEC,
        )
        self.stop_all_cameras = StopAllCameras(cams, inf, scan)
        self.start_zone_cameras = StartZoneCameras(cams)
        self.stop_zone_cameras = StopZoneCameras(cams, inf, scan)
        self.get_camera_status = GetCameraStatus(cams, scan)
        self.confirm_ready = ConfirmReady(cams, inf, state, scan)
        self.pause_scan = PauseScan(inf, scan)
        self.on_dispatch_success = OnDispatchSuccess(inf, state, scan)

        self.list_camera_configs = ListCameraConfigs(self.camera_configs)
        self.list_camera_configs_by_area = ListCameraConfigsByArea(self.camera_configs)
        self.create_camera_config = CreateCameraConfig(self.camera_configs)
        self.update_camera_config = UpdateCameraConfig(self.camera_configs)
        self.delete_camera_config = DeleteCameraConfig(self.camera_configs)

        self.get_nodes_by_zone = GetNodesByZone(self.nodes_repo)
        self.get_node_by_id = GetNodeById(self.nodes_repo)
        self.set_node_enabled = SetNodeEnabled(self.nodes_repo, state)
        self.update_node_priority = UpdateNodePriority(self.nodes_repo)
        self.create_node = CreateNode(self.nodes_repo)
        self.delete_node = DeleteNode(self.nodes_repo)
        self.disable_camera_nodes = DisableCameraNodes(self.nodes_repo, state)
        self.enable_camera_nodes = EnableCameraNodes(self.nodes_repo)

        self.get_pairs_by_zone = GetPairsByZone(self.pairs_repo)
        self.set_pair_enabled = SetPairEnabled(self.pairs_repo)
        self.create_pair = CreatePair(self.pairs_repo)
        self.delete_pair = DeletePair(self.pairs_repo)

        self.start_runtime = StartRuntime(self.runtime_control)
        self.stop_runtime = StopRuntime(self.runtime_control)
        self.get_runtime_status = GetRuntimeStatus(self.runtime_control)
        self.reload_runtime = ReloadRuntime(self.runtime_control)

        self.run_dispatch_cycle = RunDispatchCycle(state, self.dispatch_gateway)


container = AppContainer()
