# Phase 7 — Củng cố

**Status:** Done

## Mục tiêu

Khóa test độc lập + hết god folder; bỏ abstraction tạm.

Quyết định đã chốt:

1. **Facade** — bỏ `StateManager`; runtime dùng `NodeState` trực tiếp; xóa `core/`
2. **`points` dict** — **giữ** nội bộ domain (không method-only)
3. **Code chết** — xóa `utils/data.py`
4. **CI** — không thêm GitHub Actions ở phase này
5. **Dependency rule** — pytest scan `domain/` không import tầng ngoài
6. **Test gap** — boundary + smoke không còn `core/` / `service/`
7. **Docs** — README toàn bộ Done

## Vì sao không refactor `points` sang method-only (mục 2)

Không phải “thiếu một phase kiến trúc”. Dict đã nằm **trong** `NodeState`. Method-only nghĩa là cấm caller đọc/ghi `state.points[...]` / `ready_start_list.add(...)`.

Phải đổi:

- `domain/reset_policy.py` (mutate `points` / ready lists)
- `NodeStateAdapter.has_node` (`node_id in points`)
- `PairManager.make_pairs` (đọc `ready_start_list`)
- Test domain/application đang set `ready_start_list.add` / assert `points[..]["flag"]`

Lợi ích: encapsulation chặt hơn. Rủi ro: nhiều chỗ đổi, dễ regress timer/flag, **không** giúp unit test độc lập thêm (đã test được không GPU). Nên giữ dict nội bộ.

## Checklist thay đổi (đã làm)

- [x] `RuntimeService` tạo `NodeState` (không `StateManager`)
- [x] `NodeStateAdapter` nhận `NodeState` trực tiếp (bỏ `domain_state`)
- [x] `PairManager.process_ends(warn=logger.warning)` — giữ log khi mất mapping
- [x] Xóa folder `core/`
- [x] Xóa `utils/data.py`
- [x] `tests/domain/test_layer_boundaries.py`
- [x] Không thêm CI workflow (4B)

## Không làm ở Phase 7

- GitHub Actions pytest
- Encapsulate `points` thành API method-only
- import-linter / tool ngoài

## Exit criteria

- [x] pytest domain + application không cần RTSP/model
- [x] Không còn `core/` / `service/`
- [x] Dependency rule enforce bằng test scan import

## Luồng giả định verify

1. Startup: `RuntimeService` → `NodeState(...)` → inject vào `PairManager` + `CameraManager` + `container.bind_runtime`
2. Camera thread vẫn `get_state_nodes`; dispatch vẫn `set_pair_used` trên cùng object domain
3. `python -m pytest tests/application tests/domain tests/infrastructure -q`
