"""
Batch dispatch policy — confirm-dispatch / cols / accessible head.

Batch = các start đã isReady lúc người dùng confirm-dispatch.
Chỉ start trong batch mới được gửi ICS; mỗi start tối đa 1 lần.

Stack-based column ordering:
- Mỗi col là một lane vật lý, AMR vào từ entrance (priority nhỏ nhất).
- Head = node đầu tiên trong pending mà TẤT CẢ nodes phía trước (priority nhỏ hơn)
  đều TRỐNG (không trong pending = đã dispatch/skip HOẶC không có hàng từ đầu).
- Head ∈ pending → gửi (trust; không phụ thuộc ready lúc gửi).
- Không có head accessible → chờ hoặc sang col tiếp theo.
- Zone đang lock_system → chờ unlock (không skip/gửi).

Node mới ngoài batch: không halt — chờ confirm batch sau.

Pure functions: no camera manager, inference engine, or threading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from domain.dispatch.priority import (
    StartMetaMap,
    col_of,
    col_sort_key,
    start_sort_key,
    zone_of,
)

Pair = Tuple[str, ...]


@dataclass(frozen=True)
class BatchSnapshot:
    nodes: frozenset
    sum_request: int = 0
    active: bool = True
    dispatched: frozenset = field(default_factory=frozenset)
    skipped: frozenset = field(default_factory=frozenset)

    @property
    def size(self) -> int:
        return len(self.nodes)

    @property
    def pending(self) -> frozenset:
        return self.nodes - self.dispatched - self.skipped

    @property
    def remaining(self) -> int:
        return len(self.pending)


def start_batch(ready_nodes: Iterable[str]) -> BatchSnapshot:
    """Người dùng confirm-dispatch: start đang isReady làm batch."""
    return BatchSnapshot(nodes=frozenset(ready_nodes), sum_request=0, active=True)


def record_dispatch_success(
    batch: BatchSnapshot, node_id: Optional[str] = None
) -> BatchSnapshot:
    """Sau mỗi dispatch thành công — đánh dấu start đã gửi."""
    if not batch.active:
        return batch
    dispatched = batch.dispatched | {node_id} if node_id else batch.dispatched
    return BatchSnapshot(
        nodes=batch.nodes,
        sum_request=len(dispatched) + len(batch.skipped & batch.nodes),
        active=True,
        dispatched=dispatched,
        skipped=batch.skipped,
    )


def record_skip(batch: BatchSnapshot, node_ids: Iterable[str]) -> BatchSnapshot:
    """Đánh dấu skip thủ công. Chỉ nodes trong batch ảnh hưởng remaining."""
    if not batch.active:
        return batch
    extra = frozenset(n for n in node_ids if n in batch.nodes) - batch.dispatched
    if not extra:
        return batch
    skipped = batch.skipped | extra
    return BatchSnapshot(
        nodes=batch.nodes,
        sum_request=len(batch.dispatched) + len(skipped & batch.nodes),
        active=True,
        dispatched=batch.dispatched,
        skipped=skipped,
    )


def should_auto_pause(batch: BatchSnapshot) -> bool:
    """True khi không còn node trong batch chờ gửi/skip."""
    return batch.active and batch.remaining <= 0


def busy_zones(
    locked_starts: Iterable[str], start_meta: Optional[StartMetaMap] = None
) -> Set[str]:
    """Zone đang có start lock_system — tối đa 1 lệnh/zone."""
    return {zone_of(nid, start_meta) for nid in locked_starts}


def _done(batch: BatchSnapshot) -> Set[str]:
    return set(batch.dispatched) | set(batch.skipped)


def mongo_starts_by_zone_col(
    start_meta: Optional[StartMetaMap],
) -> Dict[str, Dict[str, List[str]]]:
    """
    zone_id → col_id → starts sorted by priority ASC.
    Dùng TOÀN BỘ start trong meta (Mongo), không chỉ batch.
    """
    by: Dict[str, Dict[str, List[str]]] = {}
    for nid in start_meta or {}:
        z = zone_of(nid, start_meta)
        c = col_of(nid, start_meta)
        by.setdefault(z, {}).setdefault(c, []).append(nid)
    for z, cols in by.items():
        for c, nodes in cols.items():
            cols[c] = sorted(nodes, key=lambda n: start_sort_key(n, start_meta))
    return by


def col_head_in_zone(
    zone_id: str,
    col_id: str,
    batch: BatchSnapshot,
    start_meta: Optional[StartMetaMap],
) -> Optional[str]:
    """
    Head = node đầu tiên trong pending mà TẤT CẢ nodes phía trước đều TRỐNG.

    Layout vật lý (stack-based):
        entrance (priority nhỏ) ←→ deep (priority lớn)
        [1] - [2] - [3]   ← AMR vào từ 1

    - Node không trong pending = TRỐNG (đã dispatch/skip HOẶC không có hàng)
    - AMR chỉ lấy được node X khi tất cả nodes phía trước X đều trống
    - Return None nếu không có node nào accessible trong col
    """
    cols = mongo_starts_by_zone_col(start_meta).get(zone_id) or {}
    nodes = cols.get(col_id) or []  # sorted by priority ASC (entrance → deep)
    pending = set(batch.pending)

    for i, nid in enumerate(nodes):
        if nid not in pending:
            # Node này trống (không có hàng hoặc đã xử lý) → lối đi thông
            continue

        # nid ∈ pending: kiểm tra các node phía trước (priority nhỏ hơn)
        nodes_before = nodes[:i]
        blocked = any(n in pending for n in nodes_before)

        if not blocked:
            # Tất cả nodes phía trước đều trống → head accessible
            return nid

    # Không có node nào accessible (tất cả pending đều bị chặn)
    return None


def ordered_cols_in_zone(
    zone_id: str, start_meta: Optional[StartMetaMap]
) -> List[str]:
    cols = mongo_starts_by_zone_col(start_meta).get(zone_id) or {}
    return sorted(cols.keys(), key=col_sort_key)


def zones_touching_batch(
    batch: BatchSnapshot, start_meta: Optional[StartMetaMap]
) -> List[str]:
    zones = {zone_of(n, start_meta) for n in batch.nodes}
    # Cũng xét zone có trong meta nếu batch rỗng — không cần
    return sorted(zones)


@dataclass(frozen=True)
class ColPlan:
    """Kết quả một vòng: starts được phép gửi + nodes trong batch cần skip."""

    allow_starts: frozenset = field(default_factory=frozenset)
    skip_nodes: frozenset = field(default_factory=frozenset)
    col_heads: Dict[str, str] = field(default_factory=dict)  # "zone|col" → head
    waiting: List[Dict[str, str]] = field(default_factory=list)


def plan_col_dispatch(
    batch: BatchSnapshot,
    start_meta: Optional[StartMetaMap] = None,
    locked_starts: Iterable[str] = (),
) -> ColPlan:
    """
    Tính allow cho một vòng gate (stack-based accessible head).

    Với mỗi zone không busy:
      Duyệt col theo col_id ASC.
      Head = node đầu tiên trong pending có lối đi thông từ entrance.
      - head found → allow head, dừng zone (1 lệnh/zone).
      - head None → col không có gì accessible, sang col tiếp.
      - zone busy → waiting, không allow.

    Không còn "hole skip" vì:
      - Node không trong pending = TRỐNG = lối đi thông
      - Head luôn trong pending (nếu có)
    """
    if not batch.active or batch.remaining <= 0:
        return ColPlan()

    busy = busy_zones(locked_starts, start_meta)
    allow: Set[str] = set()
    heads: Dict[str, str] = {}
    waiting: List[Dict[str, str]] = []

    for zone in zones_touching_batch(batch, start_meta):
        if zone in busy:
            # Head của col đang active (chưa xong) để FE biết đang chờ unlock
            for col in ordered_cols_in_zone(zone, start_meta):
                head = col_head_in_zone(zone, col, batch, start_meta)
                if head is None:
                    continue
                heads[f"{zone}|{col}"] = head
                waiting.append(
                    {
                        "zoneId": zone,
                        "colId": col,
                        "nodeId": head,
                        "reason": "zone_locked",
                    }
                )
                break
            continue

        for col in ordered_cols_in_zone(zone, start_meta):
            head = col_head_in_zone(zone, col, batch, start_meta)
            if head is None:
                # Col không có node accessible (tất cả pending bị chặn hoặc hết)
                continue
            heads[f"{zone}|{col}"] = head
            # head luôn trong pending theo định nghĩa mới của col_head_in_zone
            allow.add(head)
            break  # 1 lệnh / zone

    return ColPlan(
        allow_starts=frozenset(allow),
        skip_nodes=frozenset(),  # Không còn skip logic
        col_heads=heads,
        waiting=waiting,
    )


def allowed_pairs(
    batch: BatchSnapshot,
    pairs: Sequence[Pair],
    start_meta: Optional[StartMetaMap] = None,
    locked_starts: Iterable[str] = (),
    *,
    plan: Optional[ColPlan] = None,
) -> List[Pair]:
    """
    Lọc pairs theo ColPlan.allow_starts.
    Caller nên apply plan.skip_nodes vào batch trước hoặc cùng vòng.
    """
    if not batch.active or batch.remaining <= 0:
        return []
    pl = plan or plan_col_dispatch(batch, start_meta, locked_starts)
    if not pl.allow_starts:
        return []
    allowed = [p for p in pairs if p[0] in pl.allow_starts]
    return allowed[: batch.remaining]


def dispatchable_starts(
    ready_starts: Iterable[str], validate_pairs: Iterable[Sequence[str]]
) -> Set[str]:
    """Start ready có cặp normal (start, end). Bỏ start_empty — không thuộc batch."""
    normal = {p[0] for p in validate_pairs if len(p) == 2}
    return set(ready_starts) & normal


def waiting_for(
    batch: BatchSnapshot,
    start_meta: Optional[StartMetaMap],
    ready_starts: Iterable[str] = (),
    locked_starts: Iterable[str] = (),
) -> List[Dict[str, str]]:
    """Heads đang chờ (zone lock) hoặc head ∈ batch nhưng chưa có end pair (UI)."""
    if not batch.active:
        return []
    plan = plan_col_dispatch(batch, start_meta, locked_starts)
    out = list(plan.waiting)
    # Head được allow nhưng chưa có trong pairs sẽ hiện ở pending_pairs riêng
    _ = ready_starts  # giữ chữ ký tương thích; trust không cần ready
    return out


def stuck_nodes(batch: BatchSnapshot, ready_starts: Iterable[str]) -> List[str]:
    """
    Start trong batch, chưa gửi/skip, không còn isReady.
    Chỉ mang tính thông tin UI — trust vẫn cho gửi.
    """
    if not batch.active:
        return []
    ready = set(ready_starts)
    return sorted(n for n in batch.pending if n not in ready)


def find_new_nodes(
    current_nodes: Iterable[str],
    snapshot_nodes: Iterable[str],
) -> Set[str]:
    """Start hiện có nhưng không có trong batch — chỉ báo cáo, không halt."""
    return set(current_nodes) - set(snapshot_nodes)


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


# --- Tương thích tạm (zone_heads dùng trong log/test cũ) ---


def zone_heads(
    batch: BatchSnapshot, start_meta: Optional[StartMetaMap] = None
) -> Dict[str, str]:
    """
    Deprecated helper: zone → allow head hiện tại (từ ColPlan).
    """
    plan = plan_col_dispatch(batch, start_meta, ())
    by_zone: Dict[str, str] = {}
    for key, head in plan.col_heads.items():
        zone = key.split("|", 1)[0]
        if zone not in by_zone and head in batch.pending:
            by_zone[zone] = head
    for start in plan.allow_starts:
        by_zone[zone_of(start, start_meta)] = start
    return by_zone
