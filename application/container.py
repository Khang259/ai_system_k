"""Composition root — wire ports into use cases. Singleton module-level `container`."""
from __future__ import annotations

from application.auth import GetMe, Login, Logout, RefreshSession
from application.cameras import (
    CancelBatch,
    ConfirmDispatch,
    DeleteWebrtcSession,
    GetCameraPreview,
    GetCameraPreviewMeta,
    GetWebrtcGrid,
    OfferWebrtc,
    OnDispatchSuccess,
    PauseScan,
    StartAllCameras,
    StartScan,
    StartZoneCameras,
    StopAllCameras,
    StopZoneCameras,
    WebrtcSessionRegistry,
)
from application.fe_api import (
    CreateCamera,
    CreatePairFe,
    CreateRoi,
    DeleteCamera,
    DeletePairFe,
    DeleteRoi,
    DownloadMapZip,
    GetAuditLogs,
    GetCameras,
    GetCompress,
    GetNodePairs,
    GetNodeRuntimeState,
    GetNodes,
    GetNotifications,
    GetPollSnapshot,
    GetRois,
    GetSnapshotImage,
    GetSnapshotsByOrder,
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
    SetPairEnabledFe,
    Unlock,
    UpdateCamera,
    UpdateNode,
    UpdatePairFe,
    UpdateRoi,
)
from application.dispatch.active_task_hub import ActiveTaskHub
from application.dispatch.active_tasks import (
    GetActiveTasks,
    StartPriorityReader,
    TrackDispatchedTask,
    UnlockByOrderStatus,
)
from application.null_ports import (
    NullActionAudit,
    NullSystemActionAudit,
    NullAuthAudit,
    NullCameraConfigRepo,
    NullCameraRuntime,
    NullDbHealth,
    NullDispatchGateway,
    NullIcsOrderQuery,
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
    NullSnapshotDocStore,
    NullTokenIssuer,
    NullUserRepo,
    NullWebrtcRunner,
    NullZoneRepo,
)
from application.runtime import (
    GetHealth,
    GetRuntimeStatus,
    ReloadRuntime,
    RuntimeStateHub,
    StartRuntime,
    StopRuntime,
)
from application.dispatch.dispatch_gate import DispatchGate
from application.dispatch.pending_pairs import GetPendingPairs
from application.scan_session import ScanSession
from application.state.reset_flags import ResetFlagsByOrder


class AppContainer:
    def __init__(self) -> None:
        self.scan_session = ScanSession()
        self.dispatch_gate = DispatchGate(self.scan_session, self._runtime_meta)
        self.cameras = NullCameraRuntime()
        self.inference = NullInference()
        self.state = NullNodeStateStore()
        self.camera_configs = NullCameraConfigRepo()
        self.pairs_repo = NullPairsRepo()
        self.nodes_repo = NullNodeRepo()
        self.zones_repo = NullZoneRepo()
        self.runtime_control = NullRuntimeControl()
        self.dispatch_gateway = NullDispatchGateway()
        self.ics_order_query = NullIcsOrderQuery()
        self.active_task_hub = ActiveTaskHub()
        # Priority start nạp lúc runtime start — rỗng khi runtime chưa chạy
        self.start_meta = {}
        self.db_health = NullDbHealth()
        self.webrtc_runner = NullWebrtcRunner()
        self.users = NullUserRepo()
        self.refresh_tokens = NullRefreshTokenStore()
        self.auth_audit = NullAuthAudit()
        self.action_audit = NullActionAudit()
        self.system_action_audit = NullSystemActionAudit()
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
        self.snapshot_docs = NullSnapshotDocStore()
        self.node_lock_sync = NullNodeLockSync()
        self.map_versions = NullMapVersionStore()
        self.map_state = NullMapStateStore()
        self.map_zip_store = None
        self.runtime_state_hub = RuntimeStateHub(debounce_ms=150)
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

        Cần thiết để `/api/v1/runtime/get_status` và `/api/v1/runtime/reload`
        vẫn dùng được khi runtime khởi động thất bại — nếu không thì chúng
        trỏ vào port rỗng và người vận hành buộc phải restart app mới thử lại.
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

    def bind_system_action_audit(self, system_action_audit) -> None:
        self.system_action_audit = system_action_audit
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
        """Gắn asyncio loop để publisher/indexer/lock/audit ghi Mongo từ thread PairManager."""
        self.notification_publisher.bind_loop(loop)
        self.snapshot_indexer.bind_loop(loop)
        self.node_lock_sync.bind_loop(loop)
        self.system_action_audit.bind_loop(loop)

    def bind_snapshot_indexer(self, repo) -> None:
        from infrastructure.storage.snapshot_indexer import SnapshotIndexer

        self.snapshot_indexer = SnapshotIndexer(repo)
        self.snapshot_docs = repo
        self._wire()
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

    def bind_ics_order_query(self, order_query) -> None:
        self.ics_order_query = order_query
        self._wire()

    def bind_start_meta(self, start_meta) -> None:
        self.start_meta = dict(start_meta or {})

    def _runtime_meta(self):
        return self.start_meta

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
        self._attach_runtime_hub()
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
        self._detach_runtime_hub()
        self.cameras = NullCameraRuntime()
        self.inference = NullInference()
        self.state = NullNodeStateStore()
        self.start_meta = {}
        self._wire()

    def _domain_node_state(self):
        sm = self.state
        return getattr(sm, "_sm", None)

    def _attach_runtime_hub(self) -> None:
        hub = self.runtime_state_hub
        domain_sm = self._domain_node_state()
        if domain_sm is not None and hasattr(domain_sm, "set_change_listener"):
            domain_sm.set_change_listener(hub.touch)
        hub.bind_snapshot(
            lambda: self.state.snapshot_points() if self.state.is_ready() else {}
        )

    def _detach_runtime_hub(self) -> None:
        domain_sm = self._domain_node_state()
        if domain_sm is not None and hasattr(domain_sm, "set_change_listener"):
            domain_sm.set_change_listener(None)
        self.runtime_state_hub.bind_snapshot(lambda: {})

    def _wire(self) -> None:
        from config.settings import settings

        self._wire_dispatch_unlock(settings)
        self._wire_cameras_runtime(settings)
        self._wire_system_runtime()
        self._wire_auth(settings)
        self._wire_fe_cameras(settings)
        self._wire_fe_nodes_pairs()
        self._wire_fe_logs_maps(settings)
        self._wire_poll()

    def _wire_dispatch_unlock(self, settings) -> None:
        state = self.state
        self.reset_flags = ResetFlagsByOrder(state)
        priorities = StartPriorityReader(self.nodes_repo, self._runtime_meta)
        self.track_dispatched_task = TrackDispatchedTask(
            self.active_task_hub, self._runtime_meta
        )
        self.get_active_tasks_v1 = GetActiveTasks(
            self.ics_order_query,
            self.active_task_hub,
            priorities,
            settings.ICS_AREA_ID,
        )
        self.unlock_by_order_status_v1 = UnlockByOrderStatus(
            self.reset_flags, self.active_task_hub, priorities
        )

    def _wire_cameras_runtime(self, settings) -> None:
        scan = self.scan_session
        cams = self.cameras
        inf = self.inference
        state = self.state
        self.start_all_cameras = StartAllCameras(
            cams,
            inf,
            wait_model_sec=settings.START_WAIT_MODEL_SEC,
            wait_stream_sec=settings.START_WAIT_STREAM_SEC,
        )
        self.stop_all_cameras = StopAllCameras(cams, inf, scan)
        self.start_zone_cameras = StartZoneCameras(cams)
        self.stop_zone_cameras = StopZoneCameras(cams, inf, scan)
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
        self.start_scan = StartScan(cams, inf)
        self.confirm_dispatch = ConfirmDispatch(inf, state, scan, self._runtime_meta)
        self.get_pending_pairs = GetPendingPairs(state, scan, self._runtime_meta)
        self.cancel_batch = CancelBatch(scan)
        self.pause_scan = PauseScan(inf, scan)
        self.on_dispatch_success = OnDispatchSuccess(scan)

    def _wire_system_runtime(self) -> None:
        self.start_runtime = StartRuntime(self.runtime_control)
        self.stop_runtime = StopRuntime(self.runtime_control)
        self.get_runtime_status = GetRuntimeStatus(self.runtime_control)
        self.reload_runtime = ReloadRuntime(self.runtime_control)
        self.get_health = GetHealth(
            self.db_health, self.runtime_control, self.webrtc_runner
        )

    def _wire_auth(self, settings) -> None:
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

    def _wire_fe_cameras(self, settings) -> None:
        cams = self.cameras
        inf = self.inference
        state = self.state
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
        self.set_camera_status_v1 = SetCameraStatus(
            self.camera_configs,
            self.nodes_repo,
            self.pairs_repo,
            cams,
            inf,
            state,
        )
        self.create_camera_v1 = CreateCamera(
            self.camera_configs,
            self.nodes_repo,
            cams,
            inf,
            res,
        )
        self.update_camera_v1 = UpdateCamera(
            self.camera_configs,
            self.nodes_repo,
            self.pairs_repo,
            cams,
            inf,
            state,
            res,
        )
        self.delete_camera_v1 = DeleteCamera(
            self.camera_configs,
            self.nodes_repo,
            self.pairs_repo,
            inf,
            state,
        )
        self.create_roi_v1 = CreateRoi(
            self.camera_configs,
            self.nodes_repo,
            settings.MODEL_WIDTH,
            settings.MODEL_HEIGHT,
            inf,
        )
        self.update_roi_v1 = UpdateRoi(
            self.camera_configs,
            self.nodes_repo,
            settings.MODEL_WIDTH,
            settings.MODEL_HEIGHT,
            inf,
        )
        self.delete_roi_v1 = DeleteRoi(
            self.camera_configs,
            self.nodes_repo,
            settings.MODEL_WIDTH,
            settings.MODEL_HEIGHT,
            inf,
            self.pairs_repo,
        )

    def _wire_fe_nodes_pairs(self) -> None:
        cams = self.cameras
        inf = self.inference
        state = self.state
        self.get_nodes_v1 = GetNodes(self.nodes_repo)
        self.update_node_v1 = UpdateNode(self.nodes_repo)
        self.set_maintenance_v1 = SetMaintenance(self.nodes_repo, state)
        self.set_lock_v1 = SetLock(self.nodes_repo, state)
        self.unlock_v1 = Unlock(self.nodes_repo, state)
        self.get_zones_v1 = GetZones(
            self.zones_repo, self.camera_configs, self.nodes_repo, cams
        )
        self.get_node_pairs_v1 = GetNodePairs(self.pairs_repo, self.nodes_repo)
        self.create_pair_v1 = CreatePairFe(
            self.pairs_repo,
            self.nodes_repo,
            self.camera_configs,
            self.runtime_control,
            inf,
        )
        self.update_pair_v1 = UpdatePairFe(
            self.pairs_repo,
            self.nodes_repo,
            self.camera_configs,
            self.runtime_control,
            inf,
        )
        self.delete_pair_v1 = DeletePairFe(
            self.pairs_repo, self.runtime_control, inf
        )
        self.set_pair_enabled_v1 = SetPairEnabledFe(
            self.pairs_repo, self.runtime_control, inf
        )

    def _wire_fe_logs_maps(self, settings) -> None:
        self.get_audit_logs_v1 = GetAuditLogs(self.audit_logs)
        self.get_user_action_logs_v1 = GetUserActionLogs(self.action_logs)
        self.get_system_action_logs_v1 = GetSystemActionLogs(self.dispatch_logs)
        self.get_notifications_v1 = GetNotifications(self.notifications)
        self.mark_notification_read_v1 = MarkNotificationRead(self.notifications)
        self.mark_all_notifications_read_v1 = MarkAllNotificationsRead(
            self.notifications
        )
        self.get_snapshot_image_v1 = GetSnapshotImage(settings.SNAPSHOT_DIR)
        self.get_snapshots_by_order_v1 = GetSnapshotsByOrder(self.snapshot_docs)

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

    def _wire_poll(self) -> None:
        self.get_node_runtime_state_v1 = GetNodeRuntimeState(self.state)
        self.get_poll_snapshot_v1 = GetPollSnapshot(
            self.get_cameras_v1,
            self.get_zones_v1,
            self.notifications,
            self.map_state,
            get_runtime_nodes=self.get_node_runtime_state_v1,
            recommended_interval_sec=2.0,
        )


container = AppContainer()
