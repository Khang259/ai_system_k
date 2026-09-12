"""Composition root — wire ports into use cases. Singleton module-level `container`."""
from __future__ import annotations

from application.scan_session import ScanSession
from application.null_ports import (
    NullActionAudit,
    NullAuthAudit,
    NullCameraConfigRepo,
    NullCameraRuntime,
    NullDbHealth,
    NullDispatchGateway,
    NullInference,
    NullMapStateStore,
    NullMapVersionStore,
    NullNodeRepo,
    NullNodeStateStore,
    NullNotificationStore,
    NullPagedLogStore,
    NullPairsRepo,
    NullPasswordHasher,
    NullRefreshTokenStore,
    NullRuntimeControl,
    NullTokenIssuer,
    NullUserRepo,
    NullWebrtcRunner,
    NullZoneRepo,
)
from application.auth.session import GetMe, Login, Logout, RefreshSession
from application.fe_api import (
    CreateRoi,
    DeleteRoi,
    DownloadMapZip,
    GetAuditLogs,
    GetCameras,
    GetCompress,
    GetNodes,
    GetNodePairs,
    GetNotifications,
    GetRois,
    GetSnapshotImage,
    GetSystemActionLogs,
    GetUserActionLogs,
    GetZones,
    ImportMap,
    ListMapVersions,
    MarkAllNotificationsRead,
    MarkNotificationRead,
    SetActiveMap,
    SetCameraStatus,
    SetLock,
    SetMaintenance,
    Unlock,
    UpdateRoi,
)
from application.fe_api.poll import GetPollSnapshot
from application.state.update_detection import UpdateDetection
from application.state.reset_flags import ResetFlagsByOrder
from application.state.get_all_points import GetAllPoints
from application.state.get_zone_state import GetZoneState
from application.cameras.start_stop import StartAllCameras, StopAllCameras
from application.cameras.zone import StartZoneCameras, StopZoneCameras
from application.cameras.get_status import GetCameraStatus
from application.cameras.preview import GetCameraPreview, GetCameraPreviewMeta
from application.cameras.webrtc_sessions import WebrtcSessionRegistry
from application.cameras.webrtc_signaling import (
    DeleteWebrtcSession,
    GetWebrtcGrid,
    OfferWebrtc,
)
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
from application.runtime.health import GetHealth


class AppContainer:
    def __init__(self) -> None:
        self.scan_session = ScanSession()
        self.cameras = NullCameraRuntime()
        self.inference = NullInference()
        self.state = NullNodeStateStore()
        self.camera_configs = NullCameraConfigRepo()
        self.pairs_repo = NullPairsRepo()
        self.nodes_repo = NullNodeRepo()
        self.zones_repo = NullZoneRepo()
        self.runtime_control = NullRuntimeControl()
        self.dispatch_gateway = NullDispatchGateway()
        self.db_health = NullDbHealth()
        self.webrtc_runner = NullWebrtcRunner()
        self.users = NullUserRepo()
        self.refresh_tokens = NullRefreshTokenStore()
        self.auth_audit = NullAuthAudit()
        self.action_audit = NullActionAudit()
        self.password_hasher = NullPasswordHasher()
        self.token_issuer = NullTokenIssuer()
        self.audit_logs = NullPagedLogStore()
        self.action_logs = NullPagedLogStore()
        self.dispatch_logs = NullPagedLogStore()
        self.notifications = NullNotificationStore()
        from infrastructure.auth.notification_publisher import NullNotificationPublisher

        self.notification_publisher = NullNotificationPublisher()
        from infrastructure.persistence.node_lock_sync import NullNodeLockSync
        from infrastructure.storage.snapshot_indexer import NullSnapshotIndexer

        self.snapshot_indexer = NullSnapshotIndexer()
        self.node_lock_sync = NullNodeLockSync()
        self.map_versions = NullMapVersionStore()
        self.map_state = NullMapStateStore()
        self.map_zip_store = None
        from config.settings import settings

        self.webrtc_sessions = WebrtcSessionRegistry(
            max_sessions=settings.WEBRTC_MAX_SESSIONS
        )
        from infrastructure.webrtc import NullWebrtcGateway

        self.webrtc_gateway = NullWebrtcGateway()
        self._wire()

    def bind_webrtc(self, gateway, runner=None) -> None:
        self.webrtc_gateway = gateway
        if runner is not None:
            self.webrtc_runner = runner
        self._wire()

    def bind_db_health(self, db_health) -> None:
        self.db_health = db_health
        self._wire()

    def bind_runtime_control(self, runtime_control) -> None:
        """
        Bind riêng phần điều khiển, không kèm camera/inference.

        Cần thiết để `/runtime/status` và `/runtime/reload` vẫn dùng được khi
        runtime khởi động thất bại — nếu không thì chúng trỏ vào port rỗng và
        người vận hành buộc phải restart app mới thử lại được.
        """
        self.runtime_control = runtime_control
        self._wire()

    def bind_auth(self, users, refresh_tokens, audit, hasher, token_issuer) -> None:
        self.users = users
        self.refresh_tokens = refresh_tokens
        self.auth_audit = audit
        self.password_hasher = hasher
        self.token_issuer = token_issuer
        self._wire()

    def bind_action_audit(self, action_audit) -> None:
        self.action_audit = action_audit
        self._wire()

    def bind_log_stores(
        self, audit_logs, action_logs, dispatch_logs, notifications
    ) -> None:
        from infrastructure.auth.notification_publisher import NotificationPublisher

        self.audit_logs = audit_logs
        self.action_logs = action_logs
        self.dispatch_logs = dispatch_logs
        self.notifications = notifications
        self.notification_publisher = NotificationPublisher(notifications)
        self._wire()

    def bind_event_loop(self, loop) -> None:
        """Gắn asyncio loop để publisher/indexer/lock ghi Mongo từ thread PairManager."""
        self.notification_publisher.bind_loop(loop)
        self.snapshot_indexer.bind_loop(loop)
        self.node_lock_sync.bind_loop(loop)

    def bind_snapshot_indexer(self, repo) -> None:
        from infrastructure.storage.snapshot_indexer import SnapshotIndexer

        self.snapshot_indexer = SnapshotIndexer(repo)
        # loop gắn lại ở bind_event_loop (gọi sau trong lifespan)

    def bind_node_lock_sync(self, repo) -> None:
        from infrastructure.persistence.node_lock_sync import NodeLockSync

        self.node_lock_sync = NodeLockSync(repo)

    def bind_map(self, versions, state, zip_store) -> None:
        self.map_versions = versions
        self.map_state = state
        self.map_zip_store = zip_store
        self._wire()

    def bind_repos(self, camera_repo, pairs_repo, node_repo, zone_repo=None) -> None:
        self.camera_configs = camera_repo
        self.pairs_repo = pairs_repo
        self.nodes_repo = node_repo
        if zone_repo is not None:
            self.zones_repo = zone_repo
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
        if isinstance(state_manager, NodeStateAdapter):
            self.state = state_manager
        else:
            self.state = NodeStateAdapter(
                state_manager, lock_sync=self.node_lock_sync
            )
        self.runtime_control = runtime_control
        self._wire()

    def unbind_runtime(self) -> None:
        self.scan_session.reset()
        for info in self.webrtc_sessions.drain():
            remote = info.get("remote")
            if remote:
                try:
                    self.webrtc_gateway.hangup(remote)
                except Exception:
                    pass
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
        self.reset_flags = ResetFlagsByOrder(state)
        self.get_all_points = GetAllPoints(state)
        self.get_zone_state = GetZoneState(state, self.nodes_repo)

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
        self.get_camera_preview = GetCameraPreview(cams)
        self.get_camera_preview_meta = GetCameraPreviewMeta(cams)
        self.offer_webrtc = OfferWebrtc(
            self.webrtc_sessions,
            cameras=cams,
            gateway=self.webrtc_gateway,
        )
        self.delete_webrtc_session = DeleteWebrtcSession(
            self.webrtc_sessions,
            gateway=self.webrtc_gateway,
        )
        self.get_webrtc_grid = GetWebrtcGrid(self.webrtc_sessions)
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
        self.get_health = GetHealth(
            self.db_health, self.runtime_control, self.webrtc_runner
        )

        self.login = Login(
            self.users,
            self.token_issuer,
            self.refresh_tokens,
            self.password_hasher,
            self.auth_audit,
            max_failed=settings.LOGIN_MAX_FAILED,
            lockout_min=settings.LOGIN_LOCKOUT_MIN,
        )
        self.logout = Logout(self.refresh_tokens, self.auth_audit)
        self.refresh_session = RefreshSession(
            self.refresh_tokens, self.users, self.token_issuer
        )
        self.get_me = GetMe(self.users)

        res = f"{settings.MODEL_WIDTH}x{settings.MODEL_HEIGHT}"
        self.get_cameras_v1 = GetCameras(
            self.camera_configs, self.nodes_repo, cams, res
        )
        self.get_rois_v1 = GetRois(
            self.camera_configs,
            self.nodes_repo,
            settings.MODEL_WIDTH,
            settings.MODEL_HEIGHT,
        )
        self.set_camera_status_v1 = SetCameraStatus(self.camera_configs, cams)
        self.create_roi_v1 = CreateRoi(
            self.camera_configs,
            self.nodes_repo,
            settings.MODEL_WIDTH,
            settings.MODEL_HEIGHT,
        )
        self.update_roi_v1 = UpdateRoi(
            self.camera_configs,
            self.nodes_repo,
            settings.MODEL_WIDTH,
            settings.MODEL_HEIGHT,
        )
        self.delete_roi_v1 = DeleteRoi(
            self.camera_configs,
            self.nodes_repo,
            settings.MODEL_WIDTH,
            settings.MODEL_HEIGHT,
        )
        self.get_nodes_v1 = GetNodes(self.nodes_repo)
        self.set_maintenance_v1 = SetMaintenance(self.nodes_repo, state)
        self.set_lock_v1 = SetLock(self.nodes_repo, state)
        self.unlock_v1 = Unlock(self.nodes_repo, state)
        self.get_zones_v1 = GetZones(
            self.zones_repo, self.camera_configs, self.nodes_repo, cams
        )
        self.get_node_pairs_v1 = GetNodePairs(self.pairs_repo, self.nodes_repo)

        self.get_audit_logs_v1 = GetAuditLogs(self.audit_logs)
        self.get_user_action_logs_v1 = GetUserActionLogs(self.action_logs)
        self.get_system_action_logs_v1 = GetSystemActionLogs(self.dispatch_logs)
        self.get_notifications_v1 = GetNotifications(self.notifications)
        self.mark_notification_read_v1 = MarkNotificationRead(self.notifications)
        self.mark_all_notifications_read_v1 = MarkAllNotificationsRead(
            self.notifications
        )
        self.get_snapshot_image_v1 = GetSnapshotImage(settings.SNAPSHOT_DIR)

        from infrastructure.storage.map_zip_store import MapZipStore

        zip_store = self.map_zip_store or MapZipStore(settings.MAP_STORAGE_DIR)
        self.map_zip_store = zip_store
        self.import_map_v1 = ImportMap(
            self.map_versions,
            self.map_state,
            zip_store,
            keep=settings.MAP_VERSION_KEEP,
            max_upload_mb=settings.MAP_MAX_UPLOAD_MB,
        )
        self.list_map_versions_v1 = ListMapVersions(self.map_versions, self.map_state)
        self.set_active_map_v1 = SetActiveMap(self.map_versions, self.map_state)
        self.get_compress_v1 = GetCompress(
            self.map_versions, self.map_state, zip_store
        )
        self.download_map_zip_v1 = DownloadMapZip(
            self.map_versions, self.map_state, zip_store
        )
        self.get_poll_snapshot_v1 = GetPollSnapshot(
            self.get_cameras_v1,
            self.get_zones_v1,
            self.notifications,
            self.map_state,
            recommended_interval_sec=2.0,
        )


container = AppContainer()
