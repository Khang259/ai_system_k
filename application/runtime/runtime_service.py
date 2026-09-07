"""
Runtime Service — composition root helper: start/stop vision + dispatch + state.

Wire concrete infrastructure vào AppContainer; gọi từ app lifespan.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from config.settings import settings
from domain.node_state import NodeState
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

        snapshot_store = None
        if settings.ENABLE_SNAPSHOTS:
            snapshot_store = SnapshotFsStore(
                snapshot_dir=settings.SNAPSHOT_DIR,
                quality=settings.SNAPSHOT_QUALITY,
            )

        ics_gateway = HttpDispatchGateway(
            ics_url=settings.ICS_URL,
            retry=settings.ICS_RETRY_TIMES,
            delay=settings.ICS_RETRY_DELAY,
        )
        container.bind_dispatch_gateway(ics_gateway)

        pair_mgr = PairManager(
            state_manager=sm,
            validate_pairs=validate_pairs,
            strategy=SingleDispatch(DispatchService(ics_gateway)),
            dispatch_service=DispatchService(ics_gateway),
            snapshot_manager=snapshot_store,
            on_dispatch_success=lambda node_id: container.on_dispatch_success.execute(node_id),
        )
        pair_mgr.start()

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
        inference_eng.start()

        cam_mgr = CameraManager(
            cameras_config=cameras,
            state_manager=sm,
            inference_engine=inference_eng,
            snapshot_manager=snapshot_store,
        )
        cam_mgr.start()

        self._components = {
            "state_manager": sm,
            "pair_manager": pair_mgr,
            "snapshot_manager": snapshot_store,
            "inference_engine": inference_eng,
            "camera_manager": cam_mgr,
        }

        container.bind_runtime(cam_mgr, inference_eng, sm, runtime_control=self)

        self._running = True
        self._started_at = time.time()

        logger.info(f"Runtime started — cameras={len(cameras)}, pairs={len(validate_pairs)}")
        return self.status()

    def stop(self) -> Dict[str, Any]:
        if not self._running:
            return self.status()

        for name in ["pair_manager", "camera_manager", "inference_engine"]:
            comp = self._components.get(name)
            if comp:
                try:
                    comp.stop()
                except Exception as e:
                    logger.warning(f"Error stopping {name}: {e}")

        container.unbind_runtime()

        self._components = {}
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
