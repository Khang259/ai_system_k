"""
Health check — Mongo + runtime + MediaMTX.

MediaMTX là optional (app vẫn chạy khi thiếu binary) nên KHÔNG tính vào
healthy; chỉ report để người vận hành thấy. Mongo và runtime là bắt buộc.
"""
from __future__ import annotations

from application.ports import DbHealthPort, RuntimeControl, WebrtcRunnerPort
from application.result import UseCaseResult


class GetHealth:
    def __init__(
        self,
        db: DbHealthPort,
        runtime: RuntimeControl,
        webrtc_runner: WebrtcRunnerPort,
    ) -> None:
        self._db = db
        self._runtime = runtime
        self._runner = webrtc_runner

    async def execute(self) -> UseCaseResult:
        mongo_ok = await self._db.ping()

        try:
            runtime_running = bool(self._runtime.status().get("running", False))
        except Exception:
            runtime_running = False

        try:
            webrtc = self._runner.status()
        except Exception:
            webrtc = {"alive": False, "owned": False, "watchdog": False}

        data = {
            "service": "AMR Camera System",
            "mongo": mongo_ok,
            "runtime_running": runtime_running,
            "webrtc": webrtc,
        }

        if mongo_ok and runtime_running:
            return UseCaseResult.ok(status="ok", **data)

        missing = []
        if not mongo_ok:
            missing.append("mongo")
        if not runtime_running:
            missing.append("runtime")
        return UseCaseResult.fail(
            f"degraded: {', '.join(missing)} không sẵn sàng",
            status="degraded",
            **data,
        )
