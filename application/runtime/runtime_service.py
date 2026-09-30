"""
Runtime Service — composition root helper: start/stop vision + dispatch + state.

Wire concrete infrastructure vào AppContainer; gọi từ app lifespan.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from config.settings import settings
from domain.node_state import NodeState
from infrastructure.adapters import NodeStateAdapter
from infrastructure.dispatch.pair_manager import PairManager, SingleDispatch
from application.dispatch.dispatch_service import DispatchService
from infrastructure.storage.snapshot_fs import SnapshotFsStore
from infrastructure.vision.camera_manager import CameraManager
from infrastructure.vision.inference_engine import InferenceEngine
from infrastructure.ics.http_dispatch_gateway import HttpDispatchGateway
from infrastructure.persistence.camera_repository import camera_repository
from infrastructure.persistence.pairs_repository import pairs_repository
from application.container import container
from utils.setup_log import setup_logger

logger = setup_logger("runtime_service", "logs/runtime_service/log")


class RuntimeService:
    def __init__(self):
        self._components: Dict[str, Any] = {}
        self._running = False
        self._started_at: Optional[float] = None

    async def start(self) -> Dict[str, Any]:
        if self._running:
            return self.status()

        cameras = await camera_repository.get_all()
        if not cameras:
            logger.warning("No cameras found — please check the database!")

        validate_pairs = await pairs_repository.get_as_tuples()
        if not validate_pairs:
            logger.warning("No pairs found")

        logger.info(f"Loaded {len(cameras)} cameras, {len(validate_pairs)} pairs")

        sm = NodeState(
            validate_pairs,
            start_ready_after_sec=settings.START_READY_AFTER_SEC,
            end_ready_after_sec=settings.END_READY_AFTER_SEC,
            end_flag_reset_after_sec=settings.END_FLAG_RESET_AFTER_SEC,
        )

        ics_gateway = HttpDispatchGateway(
            ics_url=settings.ICS_URL,
            retry=settings.ICS_RETRY_TIMES,
            delay=settings.ICS_RETRY_DELAY,
        )
        container.bind_dispatch_gateway(ics_gateway)

        # Ghi từng component vào _components NGAY sau khi start, không gom lại
        # ở cuối: nếu bước sau nổ thì nhánh except mới dọn được thứ đã kịp chạy.
        # Gom ở cuối thì thread + VRAM rò rỉ, và reload sẽ tạo InferenceEngine
        # thứ hai chiếm thêm VRAM.
        self._components = {"state_manager": sm}
        try:
            inference_eng = InferenceEngine(
                model_path=settings.MODEL_PATH,
                max_queue_size=settings.INFERENCE_MAX_QUEUE_SIZE,
                max_batch_size=settings.INFERENCE_MAX_BATCH_SIZE,
                batch_timeout=settings.INFERENCE_BATCH_TIMEOUT,
                num_streams=settings.INFERENCE_NUM_STREAMS,
                initial_paused=True,
                use_preallocated_queue=settings.INFERENCE_USE_PREALLOCATED_QUEUE,
                height=settings.MODEL_HEIGHT,
                width=settings.MODEL_WIDTH,
                enable_profiler=settings.ENABLE_TORCH_PROFILER,
            )
            self._components["inference_engine"] = inference_eng
            inference_eng.start()

            # CameraManager trước — nó implement FrameProvider cho snapshot
            cam_mgr = CameraManager(
                cameras_config=cameras,
                state_manager=sm,
                inference_engine=inference_eng,
            )
            self._components["camera_manager"] = cam_mgr
            cam_mgr.start()

            # SnapshotFsStore cần frame_provider (CameraManager)
            snapshot_store = None
            if settings.ENABLE_SNAPSHOTS:
                snapshot_store = SnapshotFsStore(
                    frame_provider=cam_mgr,
                    snapshot_dir=settings.SNAPSHOT_DIR,
                    quality=settings.SNAPSHOT_QUALITY,
                    indexer=container.snapshot_indexer,
                )
            self._components["snapshot_manager"] = snapshot_store

            state_adapter = NodeStateAdapter(
                sm, lock_sync=container.node_lock_sync
            )
            # Hydrate lock từ Mongo (user + system) sau restart
            try:
                locked_docs = await container.nodes_repo.list_with_lock()
            except Exception:
                logger.warning(
                    "Không hydrate lock từ Mongo (DB chưa sẵn / repo null)",
                    exc_info=True,
                )
                locked_docs = []
            for doc in locked_docs:
                raw = doc.get("lock") if isinstance(doc.get("lock"), dict) else {}
                nid = doc.get("node_id")
                if not nid:
                    continue
                state_adapter.apply_persisted_lock(
                    nid,
                    user=bool(raw.get("user")),
                    system=bool(raw.get("system")),
                    order_id=raw.get("orderId"),
                )

            dispatch_svc = DispatchService(ics_gateway)

            def _on_dispatch_failed(start, end, order_id):
                container.notification_publisher.publish_dispatch_failed(
                    start, end, order_id
                )

            pair_mgr = PairManager(
                state_manager=state_adapter,
                validate_pairs=validate_pairs,
                strategy=SingleDispatch(dispatch_svc),
                dispatch_service=dispatch_svc,
                snapshot_manager=snapshot_store,
                on_dispatch_success=lambda node_id: container.on_dispatch_success.execute(
                    node_id
                ),
                on_dispatch_failed=_on_dispatch_failed,
            )
            self._components["pair_manager"] = pair_mgr
            pair_mgr.start()
        except Exception:
            logger.error("Runtime start thất bại — dọn component đã khởi động", exc_info=True)
            self._stop_components()
            raise

        container.bind_runtime(
            cam_mgr, inference_eng, state_adapter, runtime_control=self
        )

        self._running = True
        self._started_at = time.time()

        logger.info(f"Runtime started — cameras={len(cameras)}, pairs={len(validate_pairs)}")
        return self.status()

    def _stop_components(self) -> None:
        """Dừng theo thứ tự ngược lúc start. Dùng cho cả stop() và rollback."""
        for name in ["pair_manager", "camera_manager", "inference_engine"]:
            comp = self._components.get(name)
            if comp:
                try:
                    comp.stop()
                except Exception as e:
                    logger.warning(f"Error stopping {name}: {e}")
        self._components = {}

    def stop(self) -> Dict[str, Any]:
        if not self._running:
            return self.status()

        self._stop_components()
        container.unbind_runtime()

        self._running = False
        logger.info("Runtime stopped")
        return self.status()

    async def reload(self) -> Dict[str, Any]:
        self.stop()
        return await self.start()

    def status(self) -> Dict[str, Any]:
        cam_mgr = self._components.get("camera_manager")
        inference_eng = self._components.get("inference_engine")
        pair_mgr = self._components.get("pair_manager")

        cams = {"total": 0, "enabled": 0, "alive": 0}
        if cam_mgr:
            try:
                st = cam_mgr.get_status()
                cams = {
                    "total": int(st.get("total", 0)),
                    "enabled": int(st.get("enabled", 0)),
                    "alive": int(st.get("alive", 0)),
                }
            except Exception:
                pass

        inference_paused = None
        if inference_eng:
            try:
                inference_paused = bool(getattr(inference_eng, "_paused").is_set())
            except Exception:
                pass

        strategy_name = None
        if pair_mgr:
            try:
                strategy_name = pair_mgr.strategy.__class__.__name__
            except Exception:
                pass

        return {
            "running": self._running,
            "cameras": cams,
            "inference": {"paused": inference_paused},
            "strategy": strategy_name,
            "started_at": self._started_at,
        }


runtime_service = RuntimeService()
