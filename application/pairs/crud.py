from typing import Any, Dict, Optional

from application.result import UseCaseResult
from application.ports import PairsRepositoryPort


class GetPairsByZone:
    def __init__(self, repo: PairsRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, zone_id: str) -> UseCaseResult:
        pairs = await self._repo.get_by_zone(zone_id)
        return UseCaseResult.ok(zone_id=zone_id.upper(), pairs=pairs)


class SetPairEnabled:
    def __init__(self, repo: PairsRepositoryPort) -> None:
        self._repo = repo

    async def execute(
        self, start_point: str, end_point: Optional[str], enabled: bool
    ) -> UseCaseResult:
        ok = await self._repo.set_enabled(start_point, end_point, enabled)
        if not ok:
            return UseCaseResult.fail("Pair not found")
        return UseCaseResult.ok(
            start_point=start_point,
            end_point=end_point,
            enabled=enabled,
        )


class CreatePair:
    def __init__(self, repo: PairsRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, doc: Dict[str, Any]) -> UseCaseResult:
        required = {"start_point", "zone_id", "pair_type"}
        missing = required - set(doc.keys())
        if missing:
            return UseCaseResult.fail(f"Missing fields: {missing}")
        if doc["pair_type"] not in ("normal", "empty"):
            return UseCaseResult.fail("pair_type must be 'normal' or 'empty'")
        if doc["pair_type"] == "normal" and not doc.get("end_point"):
            return UseCaseResult.fail("end_point required for normal pair")

        payload = dict(doc)
        if payload["pair_type"] == "empty":
            payload["end_point"] = None
        payload.setdefault("enabled", True)
        inserted_id = await self._repo.create(payload)
        return UseCaseResult.ok(inserted_id=inserted_id)


class DeletePair:
    def __init__(self, repo: PairsRepositoryPort) -> None:
        self._repo = repo

    async def execute(
        self, start_point: str, end_point: Optional[str]
    ) -> UseCaseResult:
        ok = await self._repo.delete(start_point, end_point)
        if not ok:
            return UseCaseResult.fail("Pair not found")
        return UseCaseResult.ok(start_point=start_point, end_point=end_point)
