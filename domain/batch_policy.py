"""
Batch dispatch policy — confirm-dispatch / batch complete / new-node guard.

Batch = các start đã isReady lúc người dùng confirm-dispatch. Chỉ start trong
batch mới được gửi ICS, mỗi start tối đa 1 lần.

Strict order theo zone: mỗi zone chỉ gửi start đứng đầu hàng (head) trong số
chưa gửi. Zone đang có lệnh (lock_system) thì chờ — an toàn cả khi pair xuyên zone.

Pure functions: no camera manager, inference engine, or threading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from domain.dispatch.priority import StartMetaMap, start_sort_key


@dataclass(frozen=True)
class BatchSnapshot:
    nodes: frozenset
    sum_request: int = 0
    active: bool = True
    dispatched: frozenset = field(default_factory=frozenset)

    @property
    def size(self) -> int:
        return len(self.nodes)

    @property
    def remaining(self) -> int:
        return self.size - self.sum_request


def start_batch(ready_nodes: Iterable[str]) -> BatchSnapshot:
    """Người dùng confirm-dispatch: start đang isReady làm batch."""
    return BatchSnapshot(nodes=frozenset(ready_nodes), sum_request=0, active=True)


def record_dispatch_success(
    batch: BatchSnapshot, node_id: Optional[str] = None
) -> BatchSnapshot:
    """Sau mỗi dispatch thành công — tăng sum_request, đánh dấu start đã gửi."""
    if not batch.active:
        return batch
    dispatched = batch.dispatched | {node_id} if node_id else batch.dispatched
    return BatchSnapshot(
        nodes=batch.nodes,
        sum_request=batch.sum_request + 1,
        active=True,
        dispatched=dispatched,
    )


def should_auto_pause(batch: BatchSnapshot) -> bool:
    """True khi đã dispatch đủ (hoặc vượt) batch size."""
    return batch.active and batch.remaining <= 0


def _zone_of(node_id: str, start_meta: Optional[StartMetaMap]) -> str:
    return str(((start_meta or {}).get(node_id) or {}).get("zone_id") or "")


def zone_heads(
    batch: BatchSnapshot, start_meta: Optional[StartMetaMap] = None
) -> Dict[str, str]:
    """
    zone_id → start đứng đầu hàng trong số chưa gửi (priority ASC, rồi node_id).
    Start thiếu zone_id gom vào nhóm "".
    """
    pending = batch.nodes - batch.dispatched
    by_zone: Dict[str, List[str]] = {}
    for nid in pending:
        by_zone.setdefault(_zone_of(nid, start_meta), []).append(nid)
    return {
        zone: min(nodes, key=lambda n: start_sort_key(n, start_meta))
        for zone, nodes in by_zone.items()
    }


def busy_zones(
    locked_starts: Iterable[str], start_meta: Optional[StartMetaMap] = None
) -> Set[str]:
    """Zone đang có start lock_system — tối đa 1 lệnh/zone."""
    return {_zone_of(nid, start_meta) for nid in locked_starts}


def waiting_for(
    batch: BatchSnapshot,
    start_meta: Optional[StartMetaMap],
    ready_starts: Iterable[str],
    locked_starts: Iterable[str] = (),
) -> List[Dict[str, str]]:
    """Head của zone chưa gửi được: chưa ready hoặc zone đang có lệnh."""
    if not batch.active:
        return []
    ready = set(ready_starts)
    busy = busy_zones(locked_starts, start_meta)
    return [
        {"zoneId": zone, "nodeId": head}
        for zone, head in sorted(zone_heads(batch, start_meta).items())
        if head not in ready or zone in busy
    ]


def stuck_nodes(batch: BatchSnapshot, ready_starts: Iterable[str]) -> List[str]:
    """Start trong batch, chưa gửi, không còn isReady — nghi mất hàng."""
    if not batch.active:
        return []
    ready = set(ready_starts)
    return sorted(n for n in (batch.nodes - batch.dispatched) if n not in ready)


def allowed_pairs(
    batch: BatchSnapshot,
    pairs: Sequence[Tuple[str, ...]],
    start_meta: Optional[StartMetaMap] = None,
    locked_starts: Iterable[str] = (),
) -> List[Tuple[str, ...]]:
    """
    Cặp được phép gửi ICS:
    - batch đang mở, start thuộc batch và chưa gửi
    - start là head của zone (strict order)
    - zone không đang có lệnh (lock_system)
    Giữ thứ tự priority của `pairs`, cắt tối đa `remaining` cặp.
    """
    if not batch.active or batch.remaining <= 0:
        return []
    heads = set(zone_heads(batch, start_meta).values())
    busy = busy_zones(locked_starts, start_meta)
    allowed = [
        p
        for p in pairs
        if p[0] in heads and _zone_of(p[0], start_meta) not in busy
    ]
    return allowed[: batch.remaining]


def dispatchable_starts(
    ready_starts: Iterable[str], validate_pairs: Iterable[Sequence[str]]
) -> Set[str]:
    """Start ready có cặp normal (start, end). Bỏ start_empty — không thuộc batch."""
    normal = {p[0] for p in validate_pairs if len(p) == 2}
    return set(ready_starts) & normal


def find_new_nodes(
    current_nodes: Iterable[str],
    snapshot_nodes: Iterable[str],
) -> Set[str]:
    """Start hiện có nhưng không có trong batch ban đầu."""
    return set(current_nodes) - set(snapshot_nodes)


def should_pause_for_new_nodes(
    current_nodes: Iterable[str],
    snapshot_nodes: Iterable[str],
) -> Optional[Set[str]]:
    """
    Nếu có node mới ngoài batch → trả về set node đó (caller phải dừng batch).
    Không có → None.
    """
    new_nodes = find_new_nodes(current_nodes, snapshot_nodes)
    return new_nodes if new_nodes else None


def idle_batch() -> BatchSnapshot:
    """Trạng thái cổng đóng: chưa confirm / batch xong / bị dừng."""
    return BatchSnapshot(nodes=frozenset(), sum_request=0, active=False)


def locked_start_ids(snapshot: Mapping[str, Mapping[str, Any]]) -> Set[str]:
    """Start đang lock_system từ snapshot_points()."""
    out: Set[str] = set()
    for nid, data in snapshot.items():
        if not str(nid).startswith("start_"):
            continue
        lock = data.get("lock") or {}
        if lock.get("system"):
            out.add(str(nid))
    return out
