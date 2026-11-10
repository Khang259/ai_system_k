# Hạng mục chưa xong (gom từ các file plan cũ)

> Gom ngày 2026-11-10 từ `CHECKLIST.md`, `backlog.md`, `cleanup-checklist.md`,
> `inference-shard-polling.md`, `jpeg-preview.md`, ghi chú review trong `READ_ME.md` (các file gốc đã gỡ khỏi `docs/`).
> Mỗi mục đã được **đối chiếu lại với code** tại commit `41c95e3` — mục nào code đã làm
> hoặc không còn áp dụng thì liệt kê ở cuối file, không đưa vào danh sách việc.
> Bản gốc vẫn còn trong git history nếu cần đọc lại phân tích chi tiết.

Cập nhật khi xong một mục: đổi `[ ]` → `[x]` và ghi ngày, hoặc xoá hẳn mục.

**Thuật ngữ**
- **Batch**: tập start được chốt lúc `POST /api/v1/runtime/dispatch`; chỉ start trong batch được gửi ICS.
- **Trust**: khi batch đang mở, start trong batch được gửi **kể cả khi không còn `isReady`**.
- **Shard**: 1 trong N queue con của inference; camera `i` vào shard `i % num_shards`.
- **Letterbox**: resize giữ tỉ lệ + đệm viền (cách YOLO train), khác **stretch** (ép méo).

---

## 1. Rủi ro nghiệp vụ — cần xác minh / quyết định trước

- [ ] **Bảo trì (`isUnderMaintenance`) và `node.enabled=false` không chặn dispatch lâu dài**
  - `SetMaintenance` (`application/fe_api/nodes.py`) chỉ gọi `discard_from_ready` **một lần**.
    `NodeState.process_starts` / `process_ends` (`domain/node_state.py`) chỉ xét `lock_user` /
    `lock_system`, không biết maintenance/enabled → vòng PairManager kế tiếp (~1s) node lại vào ready.
  - Runtime chỉ lọc **pair** `enabled` lúc start (`pairs_repository.get_as_tuples`), không lọc node.
  - Việc: chốt nghĩa nghiệp vụ của maintenance/enabled; nếu phải chặn dispatch thì đưa cờ vào
    `NodeState` (giống `lock_user`) hoặc lọc khi nạp `validate_pairs`.

- [ ] **Start trong batch vẫn được gửi dù operator `set_lock` sau khi confirm**
  - `DispatchGate.trusted_starts()` trả `batch.pending`; `build_dispatch_pairs` không kiểm tra lock;
    `plan_col_dispatch` chỉ dùng `lock_system` (zone busy). → `lock.user` bật **sau** confirm bị bỏ qua.
  - Việc: quyết định có cần tôn trọng lock.user giữa batch không; nếu có → lọc trong
    `DispatchGate.filter` (`application/dispatch/dispatch_gate.py`) + test.

- [ ] **Mã status ICS đang cố định trong code**
  - `domain/models.py` `OrderStatus` (3 Canceled, 6 Running, 9 Assigned, 23 Placed). Ghi chú review:
    "status phải theo RCS từng nhà máy, không fixed".
  - Việc: đưa mã status vào `config/settings.py` (`.env`) rồi inject, nếu triển khai nhiều site.

- [ ] **Nhánh dispatch Empty / Double chưa dùng ở production**
  - `runtime_service` chỉ bind `SingleDispatch`. `EmptyDispatch`, `DoubleDispatch`,
    `build_empty_payload`, `build_double_payload`, `ICS_PROCESS_EMPTY/DOUBLE` chưa từng chạy.
  - Bug đã biết: `EmptyDispatch` bỏ `on_dispatch_success` → nếu bật, batch không đếm được lệnh empty.
  - 4 `TODO capture_pair` trong `application/dispatch/dispatch_service.py` (empty, empty flush, double, overflow).
  - Việc: chốt "chờ bật hay xoá" trước khi đụng.

- [ ] **Start 0 camera / 0 pair vẫn báo running**
  - `application/runtime/runtime_service.py` chỉ `logger.warning`. Việc: trả `degraded` trong health/status.

- [ ] **Cap 4 WebRTC session** (`WEBRTC_MAX_SESSIONS`) — chỉ đúng nếu product chốt grid 2×2.

## 2. Bảo mật / Auth

- [ ] **Webhook `POST /api/v1/external_server/unlock_by_order_status` không có xác thực**
  - Ai vào được LAN đều gỡ được `lock.system` theo `orderId`. Nếu mở ra ngoài LAN: API key tĩnh,
    mTLS, hoặc chặn ở tầng mạng (allowlist IP ICS).
- [ ] **Chưa có CRUD user** — chỉ tạo bằng `scripts/seed_users.py`; đổi mật khẩu / khoá / đổi quyền phải sửa Mongo.
- [ ] **Thiếu `.env.example`** — `JWT_SECRET` trống thì mọi token mất hiệu lực sau restart.
- [ ] **Logout không cắt access token ngay** (hở tối đa `ACCESS_TOKEN_TTL_MIN`) — chấp nhận, giảm TTL, hoặc blacklist.
- [ ] **Chuẩn hoá error code cho `/api/v1`** — hiện chỉ `{ "message": "..." }`, FE không phân nhánh máy đọc được
  (vd. thiếu quyền vs tài khoản disabled đều 403). Chốt schema `{ errorCode, message, details }` với FE trước khi code;
  sửa `presentation/deps.py`, `presentation/http_v1.py`, handler trong `app.py`.
- [ ] **`.github/CODEOWNERS` còn placeholder `@Khang259`** — GitHub bỏ qua im lặng owner không có quyền repo.

## 3. Hiệu năng GPU / inference

- [ ] **Shard polling chờ vô ích** — `infrastructure/vision/inference_engine.py` `_pop_one`
  - Shard đầu vòng round-robin được chờ trọn `timeout` (`shard_timeout = timeout if offset == 0`),
    mà shard đó là shard *kế tiếp* sau lần pop thành công → thường rỗng khi ít camera
    (`num_shards=4` cố định, dưới 4 camera luôn có shard rỗng).
  - Ước tính 1 camera: batch chỉ gom ~2 frame, mỗi batch mất trọn `INFERENCE_BATCH_TIMEOUT` (0.3s).
  - Đo 2026-09-08 (20 cam mock @6fps): `avg_size=31/32`, `timeout_hit=16%` → **chưa dính** ở tải này.
  - Việc: đo lại trên camera thật (~25fps) bằng dòng `Batch stats` trong `logs/inference_engine/`.
    Dấu hiệu dính bug: `avg_size` thấp + `timeout_hit` gần 100% + `shard_qsize` có phần tử luôn 0.
  - Hướng sửa (chọn 1): (A) quét `get_nowait()` mọi shard trước, chỉ chờ khi tất cả rỗng;
    (C) bỏ sharding, 1 queue; (D) condition variable chung. Thử nhanh: `num_shards=1`.
  - Dọn kèm: nhánh `return frame, cam_id, None` cuối `_pop_one` là code chết.

- [ ] **TRT luôn execute full batch** — `trt_yolo_engine.py` set shape `(max_batch, …)` mỗi lần,
  slot thừa zero. Đo mock: pad ~3%. Việc: xác nhận lại `avg_size` với camera thật rồi mới quyết định.

- [ ] **Preview: JPEG luôn encode cùng meta** — `camera_processor._publish_preview` encode 2 JPEG
  (raw + detect) mỗi lần có người watch, kể cả khi WebRTC chỉ cần JSON meta (`/preview/meta`).
  Việc: tách nhánh meta khỏi JPEG; sau đó cân nhắc bỏ JPEG nếu `GET /cameras/get_snapshot` không còn ai dùng.

- [ ] **ThreadPool ROI 2 worker / camera** — N camera → 2N thread. Việc: pool global có bound.
- [ ] **Throttle ROI** (tuỳ chọn) — chỉ check ROI mỗi 0.5s / N frame nếu vẫn thấy slow loop.
- [ ] **Letterbox GPU trước engine** — hiện `gpu_frame.py` stretch (`F.interpolate`) về 480×640.
  Làm khi: user báo conf thấp / box lệch, hoặc camera khác tỉ lệ 4:3.
- [ ] **Đo đạc chưa làm**: FPS + box TRT so với `predict()` (1 stream); nsys SM idle;
  `INFERENCE_NUM_STREAMS=2` có đạt speedup ≥ 1.15x không (không đạt → đặt 1).
- [ ] **Counter bổ sung** (khi cần định vị drop): `decoder_drop_count` trong `gpu_video_decoder.py`,
  `frames_put_infer_per_sec` vs `frames_decoded_per_sec`.
- [ ] **Phase 3 nâng cao** (chỉ khi Phase 1+2 chưa đủ): multiprocessing chia camera,
  overlay GPU khi >10 watcher, lock-free ring buffer.

### Test bão hoà upstream (20 → 100 RTSP) — chưa chạy

Mục tiêu: tìm `N_sat` (số camera mà upstream RTSP → decode bắt đầu nghẽn).
Điều kiện cố định: mock 640×480 @6fps, không mở WebRTC khi đo.

Mỗi bước N = 20, 30, …, 100:
1. Sửa `N_CAMERAS` trong `scripts/seed_db.py` → seed → restart app.
2. `POST /api/v1/system/start-cameras` (bật camera + inference).
3. Chạy ổn định ≥ 5 phút, ghi: slow rate (`grep "performance:" logs/camera_processor/*`),
   `put`, `%sm` (`nvidia-smi dmon -s u -d 1`), `Lost stream`, MediaMTX `reader is too slow`.
4. Verdict: **PASS** (slow < 0.5%, `%sm` ≥ 25%) · **WARN** (slow 0.5–1%) ·
   **SATURATED** (`%sm` giảm rõ khi tăng N, slow > 1%, reconnect storm) → dừng, ghi `N_sat`.

Baseline cũ (2026-08-22): N=20 `%sm` 35–40% healthy; N=100 `%sm` 15–22%, reconnect sau ~4 phút.

## 4. Dọn dẹp code

- [ ] **Log không tự chuyển file qua nửa đêm** — `utils/setup_log.py` chốt `date_str` lúc import,
  `FileHandler` giữ file suốt đời process → chạy N ngày dồn vào 1 file mang tên ngày khởi động.
  Việc: `TimedRotatingFileHandler(when="midnight")` (lưu ý đổi quy ước tên file mà `retention.py` đang dựa vào).
- [ ] **Thuật ngữ `flag` còn sót** — `flag = lock_user OR lock_system` vẫn ở `domain/node_state.py`
  (`_refresh_flag`, `snapshot_points()["flag"]`), `domain/models.py` `NodePoint.flag`,
  nhánh fallback trong `domain/reset_policy._clear_pair`. Dễ nhầm với "lock". Việc: thay bằng `blocked`
  hoặc bỏ hẳn khi FE không đọc `flag` nữa.
- [ ] **Dead code** — `domain/models.py` (`NodePoint`, `DispatchPair`, `RuntimeStatus`, `NodeType`,
  `DispatchType` không ai dùng; chỉ `OrderStatus` sống); `NullFrameProvider` (0 call site);
  settings không ai đọc: `API_SERVER_HOST/PORT`, `API_LOG_LEVEL` (`main.py` hardcode
  `192.168.50.200:8000`), `INFERENCE_MIN/OPT_BATCH_SIZE`; `camera_processor.window_name`.
- [ ] **Gộp/xoá benchmark cũ** `benchmarks/test_multistream_*.py` khi có test engine mới.
- [ ] **`null_ports.py` / `tests/application/fakes.py`** — tách khi thêm port mới thấy đau.

---

## Không làm (đã chốt, giữ để khỏi bàn lại)

- Tách 2 project CRUD / AI (2026-09-09): NodeState, ScanSession, frame CUDA phải sống cùng process.
  Đường cắt sẵn ở `infrastructure/adapters.py` nếu sau này cần.
- `send_command` (lệnh tay) + lock session — dispatch chỉ tự động.
- HLS/DASH cho preview; NVENC cho mọi camera; sync `position`/`mapPosition` từ map compress; serve PGM.

## Đã xác minh là xong / không còn áp dụng (không đưa vào danh sách)

| Mục cũ | Lý do loại |
|--------|-----------|
| Bỏ `POST /nodes/create_node` | Route đã gỡ |
| `zone/snapshot/dispatch_log_repository` 0 import | Đã dùng trong `app.py` |
| Hai UI preview (`static/preview.html`, `webrtc.html`) | Thư mục `static/` không còn |
| `/preview` JPEG passthrough độ phân giải gốc | Route `/preview` JPEG đã gỡ (gộp vào mục tách JPEG/meta) |
| `api_client` trên camera path | Đã gỡ |
| Endpoint cũ ngoài `/api/v1` không cần token | Toàn bộ route cũ đã gỡ (còn lại webhook — xem mục 2) |
| `END_FLAG_RESET_AFTER_SEC` tự reset node | Không còn trong code; `process_ends` không tự gỡ `lock_system` |
| F5-B overlay NVENC | Đã chọn hướng A (canvas + JSON meta) |
| Live WebRTC FE | Xong (F4–F6) |
