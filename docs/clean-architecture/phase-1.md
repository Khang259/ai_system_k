# Phase 1 — Domain thuần + facade + pytest

**Status:** Done

## Mục tiêu

Đưa rule nghiệp vụ vào `domain/`, test được không RTSP/model/Mongo. Giữ API runtime qua facade `StateManager`.

## Checklist thay đổi (đã làm)

### Domain mới

- [x] `domain/settings.py` — constant timer / priority fallback
- [x] `domain/node_state.py` — logic ex-`StateManager`
- [x] `domain/dispatch/priority.py` — `get_node_priority`
- [x] `domain/dispatch/pairing.py` — `build_dispatch_pairs`
- [x] `domain/batch_policy.py` — confirm-ready / auto-pause / new nodes
- [x] `domain/reset_policy.py` — webhook status `3` / `23`

### Facade & wire

- [x] `core/state_manager.py` → facade bọc `NodeState` (giữ `points` dict)
- [x] `service/runtime_service.py` truyền timer từ `config.settings`
- [x] `config/settings.py` thêm `END_FLAG_RESET_AFTER_SEC`
- [x] `core/pair_manager.py` dùng domain priority/pairing
- [x] `service/state_service.py` gọi `reset_policy`
- [x] `service/camera_service.py` dùng `batch_policy`

### Test

- [x] Thêm `pytest` (`pyproject.toml` optional `dev`)
- [x] `tests/domain/test_node_state.py`
- [x] `tests/domain/test_dispatch.py`
- [x] `tests/domain/test_batch_policy.py`
- [x] `tests/domain/test_reset_policy.py`

## Không làm ở Phase 1

- Chưa xóa `service/` / `core/`
- Chưa Port / use case (`application/` vẫn skeleton)
- Chưa đổi URL HTTP

## Exit criteria

- [x] `domain` không import torch / motor / requests
- [x] Unit test domain chạy độc lập
- [x] Caller cũ vẫn dùng `StateManager` / service như trước

---

## Luồng giả định để bạn verify (manual / đọc code)

### Tình huống A — Start vào ready

1. Detection báo `start_100` có hàng (`get_state_nodes(..., True)`).
2. Chưa đủ `START_READY_AFTER_SEC` → chưa vào `ready_start_list`.
3. Sau > 30s (hoặc giá trị config) + `process_starts()` → có trong `ready_start_list`.
4. Hàng biến mất → bị `discard` khỏi ready.

**Expect unit:** `tests/domain/test_node_state.py::test_start_enters_ready_after_threshold`

### Tình huống B — Ghép cặp theo priority

1. Ready: `start_200`, `start_100` và end tương ứng.
2. `build_dispatch_pairs` sort priority số tăng dần.
3. Kết quả: `start_100` trước `start_200`.

**Expect unit:** `test_build_dispatch_pairs_respects_priority_and_validate`

### Tình huống C — Batch scan

1. `confirm_ready` snapshot `{start_1, start_2}` → batch active.
2. Hai lần `on_dispatch_success` → `should_auto_pause` = True → pause inference (ở service).
3. Nếu xuất hiện `start_99` ngoài snapshot → pause + reset batch.

**Expect unit:** `tests/domain/test_batch_policy.py`  
**Manual API (khi có camera):** `POST /cameras/start-all` → `POST /runtime/confirm-ready` → theo dõi log `[BATCH]`

### Tình huống D — Reset webhook

1. Order có pair thường + empty (`empty_car=True`).
2. Status `3` → reset hết, xóa `order_mapping`.
3. Status `23` → chỉ reset empty; pair thường còn flag.

**Expect unit:** `tests/domain/test_reset_policy.py`  
**Manual API:** webhook state reset (route hiện có) với `orderId` + `status`

### Tình huống E — Runtime wiring timer

1. Đổi `.env` / settings `START_READY_AFTER_SEC=5`.
2. Restart app → `RuntimeService.start` tạo `StateManager` với 5s.
3. Node start ready nhanh hơn (smoke tay).

---

## Ghi chú facade

`StateManager.domain_state` expose `NodeState` để Phase 2 chuyển dần.  
Dict `points[...]` vẫn mutable từ `state_service.toggle_flag` — sẽ siết ở Phase 2/7.
