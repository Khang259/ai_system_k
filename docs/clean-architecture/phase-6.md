# Phase 6 — Storage & composition root

**Status:** Done

## Mục tiêu

Snapshot filesystem + dọn wiring; xóa shim `service/`; move dispatch runtime ra khỏi `core/`.

Quyết định đã chốt:

1. **Snapshot** — `infrastructure/storage/snapshot_fs.py`, class **`SnapshotFsStore`**
2. **`on_dispatch_success`** — inject callback vào `PairManager` / strategy (không shim `camera_service`)
3. **Shim** — xóa `service/state|node|pairs|camera_service`
4. **Composition root** — `RuntimeService` → `application/runtime/runtime_service.py`; `app.py` import từ đó
5. **`pair_manager`** — move → `infrastructure/dispatch/pair_manager.py`
6. **Test** — unit `save_pair_snapshots` (fake frame + mock `cv2.imwrite`) + callback inject
7. **Docs** — cập nhật phase-6 + README

## Checklist thay đổi (đã làm)

- [x] Move snapshot → `infrastructure/storage/snapshot_fs.py` (`SnapshotFsStore`)
- [x] Xóa `core/snapshot_manager.py`
- [x] Move `pair_manager` → `infrastructure/dispatch/`
- [x] Inject `on_dispatch_success` vào `PairManager` / `SingleDispatch` (và Double path single)
- [x] `RuntimeService` wire: `SnapshotFsStore` + callback → `container.on_dispatch_success.execute`
- [x] Move `RuntimeService` → `application/runtime/runtime_service.py`
- [x] `app.py` import `application.runtime.runtime_service`
- [x] Xóa toàn bộ folder `service/` (shim + runtime cũ)
- [x] Test snapshot + callback
- [x] Rà circular import: `container` không import `runtime_service` ở module level

## Không làm ở Phase 6

- Chưa bỏ `core/state_manager.py` facade (Phase 7)
- Empty/Double strategy vẫn chưa inject runtime mặc định (vẫn `SingleDispatch`)

## Exit criteria

- [x] Snapshot + dispatch nằm dưới `infrastructure/`
- [x] Không còn folder `service/`
- [x] `core/` chỉ còn `state_manager` facade
- [x] Startup: `app.py` → `runtime_service.start()` → bind container

## Luồng giả định verify

1. **Startup**
   - `app` lifespan → `runtime_service.start()`
   - Tạo `StateManager`, `HttpDispatchGateway`, `PairManager(SingleDispatch, on_dispatch_success=...)`, vision, optional `SnapshotFsStore`
   - `container.bind_runtime(...)`

2. **Dispatch thành công**
   - `SingleDispatch` gọi `snapshot.save_pair_snapshots` (nếu có) rồi `on_dispatch_success(start)`
   - Callback → use case `OnDispatchSuccess` (auto-pause / new nodes) — **không** qua `service/`

3. **Import boundary**
   - Không còn `from service.*`
   - `core/` chỉ facade state

4. **Test**
   ```bash
   python -m pytest tests/application tests/domain tests/infrastructure -q
   ```

## `core/` sau Phase 6

| File | Vai trò | Phase tiếp |
|------|---------|------------|
| `state_manager.py` | Facade → NodeState | **Phase 7** bỏ nếu hết caller |
