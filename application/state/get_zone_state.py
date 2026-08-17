from application.result import UseCaseResult
from application.ports import NodeStateStore, ZonePairsLookup


class GetZoneState:
    def __init__(self, state: NodeStateStore, zones: ZonePairsLookup) -> None:
        self._state = state
        self._zones = zones

    def execute(self, zone: str) -> UseCaseResult:
        if not self._state.is_ready():
            return UseCaseResult.fail("State manager not initialized")

        zone_pairs = self._zones.get_pairs(zone)
        node_ids = {nid for pair in zone_pairs for nid in pair}
        if not node_ids:
            return UseCaseResult.fail("Zone not found")

        snapshot = self._state.snapshot_points()
        nodes = {nid: snapshot[nid] for nid in node_ids if nid in snapshot}
        return UseCaseResult.ok(zone=zone.upper(), nodes=nodes)
