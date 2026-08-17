from application.result import UseCaseResult
from application.ports import RuntimeControl


class StartRuntime:
    def __init__(self, runtime: RuntimeControl) -> None:
        self._runtime = runtime

    async def execute(self) -> UseCaseResult:
        status = await self._runtime.start()
        return UseCaseResult.ok(**status)


class StopRuntime:
    def __init__(self, runtime: RuntimeControl) -> None:
        self._runtime = runtime

    def execute(self) -> UseCaseResult:
        status = self._runtime.stop()
        return UseCaseResult.ok(**status)


class GetRuntimeStatus:
    def __init__(self, runtime: RuntimeControl) -> None:
        self._runtime = runtime

    def execute(self) -> UseCaseResult:
        return UseCaseResult.ok(**self._runtime.status())


class ReloadRuntime:
    def __init__(self, runtime: RuntimeControl) -> None:
        self._runtime = runtime

    async def execute(self) -> UseCaseResult:
        status = await self._runtime.reload()
        return UseCaseResult.ok(**status)
