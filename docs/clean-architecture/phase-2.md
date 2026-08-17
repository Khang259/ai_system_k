# Phase 2 — Ports + Application use cases

**Status:** Done

## Mục tiêu

Phá God Service: một use case ≈ một hành động; test bằng fake Port (không RTSP / YOLO / Mongo).

Quyết định đã chốt:

1. Làm hết use case Phase 2 trong một mạch.
2. Routes gọi `application` trực tiếp; `service/` chỉ shim (PairManager callback) — xóa ở Phase 6.
3. `DispatchGateway` + `RunDispatchCycle` dùng fake; HTTP ICS vẫn ở `PairManager` đến Phase 4.
4. Wire singleton trong `application/container.py` + `app.py` lifespan.
5. Use case trả `UseCaseResult`; route map HTTP.
6. Mọi use case đều có unit test.

## Checklist thay đổi (đã làm)

### Ports & composition

- [x] `application/ports.py` — CameraConfig, Pairs, Nodes, CameraRuntime, Inference, NodeStateStore, DispatchGateway, RuntimeControl, ZonePairsLookup
- [x] `application/result.py` — `UseCaseResult`
- [x] `application/scan_session.py` — batch in-memory
- [x] `application/container.py` — composition root
- [x] `application/null_ports.py` — unbound trước `runtime.start()`
- [x] `infrastructure/adapters.py` — bọc repo/core hiện tại (Phase 3 sẽ chuyển persistence)

### Use cases

- [x] `application/state/` — update detection, reset flags, toggle flag, get points, get zone
- [x] `application/cameras/` — start/stop all+zone, status, confirm_ready, pause_scan, on_dispatch_success
- [x] `application/cameras_config/` — list/create/update/delete
- [x] `application/nodes/` — query, enable, priority, CRUD, disable/enable theo camera
- [x] `application/pairs/` — query, enable, CRUD
- [x] `application/runtime/` — start/stop/status/reload
- [x] `application/dispatch/run_cycle.py` — orchestration + fake gateway (chưa thay PairManager)

### Wire

- [x] `presentation/routes` gọi container use case
- [x] `app.py` `bind_repos` trước `runtime.start()`
- [x] `RuntimeService` `bind_runtime` / `unbind_runtime` — không `attach()` lên God Service
- [x] `service/*` shim (PairManager vẫn gọi `camera_service.on_dispatch_success`)
- [x] Unit test `tests/application/` với fake Port

### Dict / facade

- [x] Use case thao tác qua `NodeStateStore` (`toggle_flag`, `discard_from_ready`, `apply_reset`, …)
- [x] Facade `StateManager` vẫn tồn tại cho camera thread / PairManager

## Không làm ở Phase 2

- Chưa xóa `service/` / `core/` / `repository/`
- Chưa chuyển HTTP ICS ra adapter (Phase 4)
- Chưa move YOLO/RTSP (Phase 5)

## Exit criteria

- [x] Không còn God Service chứa CRUD + batch + runtime trong một class thật
- [x] Use case test xanh với fake
- [x] API HTTP giữ contract (success wrapper / raw status như cũ)

---

## Luồng giả định để bạn verify

### Tình huống A — Detection + toggle flag

1. `POST /detections` `{node_id: start_1, detected: true}` → `UpdateDetection` ghi `NodeState`.
2. `POST /state/flag/start_1` → `ToggleFlag` đảo flag qua Port, không mutate dict từ route.
3. Node chưa từng detect → `Node not found`.

**Expect unit:** `tests/application/test_state.py`

### Tình huống B — Reset webhook 3 / 23

1. Dispatch đã `set_pair_used` pair thường + empty cùng `ORD-1`.
2. `POST /delete-flag` status `23` → chỉ reset empty; pair thường còn flag; có `reset_pairs`.
3. Status `3` → reset hết, xóa `order_mapping`; không có `reset_pairs` trên HTTP.

**Expect unit:** `test_reset_flags_completed_and_empty`  
**Manual:** webhook AMR với `orderId` thật sau dispatch.

### Tình huống C — Confirm ready / batch / auto-pause

1. Chưa `start-all` (enabled=0) → `ConfirmReady` fail: gọi `/cameras/start-all` trước.
2. Cameras enabled + start nodes đang `state=True` → snapshot size, `inference.resume()`.
3. Mỗi dispatch thành công → `OnDispatchSuccess` (shim từ PairManager).
4. Đủ snapshot → auto-pause + reset batch.
5. Node mới ngoài snapshot → pause (tránh collision).

**Expect unit:** `tests/application/test_cameras.py`  
**Manual API:** `POST /cameras/start-all` → `POST /runtime/confirm-ready` → log `[BATCH]` (PairManager thật).

### Tình huống D — CRUD pairs / nodes / camera config

1. Tạo pair `normal` thiếu `end_point` → fail.
2. Tạo pair `empty` → `end_point=None`.
3. Disable node đang ready → `discard_from_ready`.
4. Update camera id không tồn tại → `success: false` (không bắt buộc field `error`).

**Expect unit:** `tests/application/test_crud.py`  
**Manual:** `POST /pairs/`, `POST /nodes/`, `GET /cameras/config`

### Tình huống E — Runtime status / reload

1. `GET /runtime/status` trả **raw** `{running, cameras, inference, ...}` (không bọc `success` khi OK — giữ contract cũ).
2. `POST /runtime/reload` = stop + start core; container `unbind` rồi `bind_runtime` lại.

**Expect unit:** `test_runtime_start_stop_status_reload` (fake RuntimeControl)  
**Manual:** reload khi đang chạy — cameras reconnect.

### Tình huống F — Dispatch cycle (fake gateway, chưa production)

1. Ready start+end + validate pair → `RunDispatchCycle` gọi `DispatchGateway.send`.
2. Gateway OK → `set_pair_used`.
3. Gateway fail → không set flag; `failed` trong result.

**Chưa** gắn vào PairManager loop (vẫn `requests` ICS). Phase 4 mới thay.

**Expect unit:** `tests/application/test_runtime_dispatch.py`

### Tình huống G — Unbound runtime

1. Gọi camera/state use case trước `bind_runtime` → Null Port `is_ready=False` → `"System not initialized"` / `"State manager not initialized"`.
2. Lifespan thật: `bind_repos` → `runtime.start()` → `bind_runtime` trước khi nhận request.

---

## Map HTTP → use case

| HTTP | Use case |
|------|----------|
| POST `/detections` | `UpdateDetection` |
| POST `/delete-flag` | `ResetFlagsByOrder` |
| POST `/state/flag/{id}` | `ToggleFlag` |
| GET `/state/points` | `GetAllPoints` → `{code:1000, points}` |
| GET `/state/zone/{z}` | `GetZoneState` |
| POST `/cameras/start-all` | `StartAllCameras` |
| POST `/cameras/stop-all` | `StopAllCameras` |
| POST `/cameras/{z}/start-all` | `StartZoneCameras` |
| POST `/cameras/{z}/stop-all` | `StopZoneCameras` |
| GET `/cameras/status` | `GetCameraStatus` (raw + batch) |
| GET/POST/PUT/DELETE `/cameras/config*` | cameras_config CRUD |
| `/nodes/*` | nodes use cases |
| `/pairs/*` | pairs use cases |
| GET `/runtime/status` | `GetRuntimeStatus` (raw) |
| POST `/runtime/reload` | `ReloadRuntime` (raw) |
| POST `/runtime/confirm-ready` | `ConfirmReady` |
| POST `/runtime/pause-scan` | `PauseScan` |

Nội bộ: PairManager → `camera_service.on_dispatch_success` shim → `OnDispatchSuccess`.

---

## Chạy test Phase 2

```bash
python -m pytest tests/application tests/domain -q
```

Không cần RTSP, model, Mongo.
