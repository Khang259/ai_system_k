import asyncio
import time
from typing import Any, Dict, List

from application.result import UseCaseResult
from application.ports import CameraRuntime, InferencePort
from application.scan_session import ScanSession
from infrastructure.sandbox.smoke_trail import emit


class StartAllCameras:
    """Option B: 200 khi model loaded và ≥1 camera streaming. Cam fail → warnings.

    Không auto-scan (giữ hành vi cũ / deprecate). Dùng StartCameras để bật inference.
    """

    def __init__(
        self,
        cameras: CameraRuntime,
        inference: InferencePort,
        wait_model_sec: float = 30.0,
        wait_stream_sec: float = 15.0,
        *,
        auto_scan: bool = False,
    ) -> None:
        self._cameras = cameras
        self._inference = inference
        self._wait_model_sec = wait_model_sec
        self._wait_stream_sec = wait_stream_sec
        self._auto_scan = auto_scan

    async def execute(self) -> UseCaseResult:
        if not self._cameras.is_ready():
            return UseCaseResult.fail("System not initialized")
        if not self._inference.is_ready():
            return UseCaseResult.fail("Inference not initialized")

        if not self._inference.is_model_loaded():
            loaded = await asyncio.to_thread(
                self._inference.wait_model_ready, self._wait_model_sec
            )
            if not loaded:
                err = self._inference.load_error() or "timeout waiting for model"
                return UseCaseResult.fail(f"Model not loaded: {err}")

        self._cameras.start_all()

        wait_sec = self._wait_stream_sec
        deadline = time.monotonic() + wait_sec
        status: Dict[str, Any] = self._cameras.get_status()
        while time.monotonic() < deadline:
            status = self._cameras.get_status()
            if int(status.get("streaming", 0)) >= 1:
                result = self._ok(status)
                emit(
                    "api",
                    "start_cameras" if self._auto_scan else "start_all",
                    enabled=int(status.get("enabled", 0)),
                    streaming=int(status.get("streaming", 0)),
                    autoScan=self._auto_scan,
                    hint=(
                        "Camera + inference bật — chờ isReady rồi POST /runtime/dispatch"
                        if self._auto_scan
                        else "Camera bật — inference vẫn pause; dùng /start-cameras"
                    ),
                )
                return result
            await asyncio.sleep(0.2)

        payload = self._status_payload(status)
        return UseCaseResult.fail(
            "No camera streaming (need at least 1). Check RTSP URLs.",
            **payload,
        )

    def _ok(self, status: Dict[str, Any]) -> UseCaseResult:
        if self._auto_scan:
            self._inference.resume()
        payload = self._status_payload(status)
        payload["scanning"] = bool(self._auto_scan)
        msg = "Cameras started and scanning" if self._auto_scan else "Cameras started"
        return UseCaseResult.ok(message=msg, **payload)

    def _status_payload(self, status: Dict[str, Any]) -> Dict[str, Any]:
        cameras = list(status.get("cameras") or [])
        warnings = _streaming_warnings(cameras)
        return {
            "total": int(status.get("total", 0)),
            "enabled": int(status.get("enabled", 0)),
            "streaming": int(status.get("streaming", 0)),
            "cameras": cameras,
            "warnings": warnings,
        }


class StartCameras(StartAllCameras):
    """POST /start-cameras — bật camera + tự resume inference."""

    def __init__(
        self,
        cameras: CameraRuntime,
        inference: InferencePort,
        wait_model_sec: float = 30.0,
        wait_stream_sec: float = 15.0,
    ) -> None:
        super().__init__(
            cameras,
            inference,
            wait_model_sec=wait_model_sec,
            wait_stream_sec=wait_stream_sec,
            auto_scan=True,
        )


def _streaming_warnings(cameras: List[Dict[str, Any]]) -> List[str]:
    warnings: List[str] = []
    for cam in cameras:
        if cam.get("enabled") and not cam.get("streaming"):
            cam_id = cam.get("cam_id", "?")
            err = cam.get("error") or "not streaming yet"
            warnings.append(f"{cam_id}: {err}")
    return warnings


class StopAllCameras:
    def __init__(self, cameras: CameraRuntime, inference, scan: ScanSession) -> None:
        self._cameras = cameras
        self._inference = inference
        self._scan = scan

    def execute(self) -> UseCaseResult:
        if not self._cameras.is_ready():
            return UseCaseResult.fail("System not initialized")
        self._cameras.stop_all()
        if self._inference.is_ready():
            self._inference.pause()
        self._scan.reset()
        return UseCaseResult.ok(message="All cameras disabled")
