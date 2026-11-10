# Onboarding — Business logic hiện tại & sửa ở đâu

> Viết cho người mới. Đọc từ trên xuống một lần, sau đó dùng mục 9 làm bảng tra.
> Đúng với code tại commit `41c95e3` (2026-11-10). Cài đặt / chạy app: xem `README.md`.
> Việc còn dở: [pending-tasks.md](./pending-tasks.md).

---

## 1. Hệ thống làm gì (1 phút)

Camera giám sát các **ô hàng** trong kho. AI (YOLO trên TensorRT) nhìn xem ô nào **có hàng**.
Khi operator bấm "gửi robot", backend gửi lệnh cho **ICS** (hệ thống điều phối robot AMR)
để robot chở hàng từ ô **start** sang ô **end**. Khi robot xong, ICS gọi ngược webhook để mở khoá ô.

```
Camera RTSP → GPU decode → YOLO (batch) → "ROI này có hàng?" → NodeState (RAM)
   → operator bấm Dispatch → chốt batch → mỗi giây PairManager ghép start→end → POST ICS
   → robot chạy → ICS gọi webhook 3/23 → mở khoá node → lệnh kế tiếp
```

### Thuật ngữ dùng xuyên suốt

| Thuật ngữ | Nghĩa |
|-----------|-------|
| **Node** | Một ô vật lý. Id có tiền tố: `start_xxx` (ô lấy hàng) hoặc `end_xxx` (ô trả hàng) |
| **ROI** | Hình chữ nhật `[x, y, w, h]` trên khung 640×480 của camera, gắn với 1 node |
| **Pair** | Cặp được phép `(start, end)` — robot chỉ chạy theo pair đã khai báo |
| **Zone** | Khu vực, kế thừa từ camera. Mỗi zone tối đa **1 lệnh đang chạy** |
| **Col** (`col_id`) | Một làn/hàng dọc trong zone. Robot vào từ đầu làn (priority nhỏ) |
| **Priority** | Số nguyên trên start node (Mongo), **nhỏ = gần lối vào = gửi trước**, unique trong zone |
| **detected** | Frame hiện tại AI có thấy hàng trong ROI không (dao động liên tục) |
| **isReady** | Trạng thái `detected` giữ **ổn định** đủ lâu → đủ điều kiện dispatch |
| **lock.user** | Operator khoá tay ô (persist Mongo) |
| **lock.system** | Hệ thống khoá ô sau khi gửi ICS thành công, kèm `orderId` (persist Mongo) |
| **Batch** | Tập start được chốt khi operator bấm Dispatch. Chỉ start trong batch được gửi |
| **Gate (cổng)** | Mở khi có batch đang chạy; đóng thì PairManager không gửi gì |
| **SSOT** | Single Source of Truth — một nguồn đúng duy nhất cho mỗi loại dữ liệu |

---

## 2. Mô hình cấu hình: camera → node → ROI → pair

```
Camera (zone, rtspUrl)
  └── observedNodeIds: [start_1, start_2, end_9]   ← camera quyết định node nào thuộc nó (SSOT)
        └── ROI trên camera cho từng node           ← bắt buộc trước khi tạo pair
              └── Pair (start_1 → end_9)            ← chỉ pair enabled mới được runtime nạp
```

Luật cứng (code chặn, FE phải tuân theo):

1. **1 node ↔ 1 camera.** Gán node đang thuộc camera khác → `409`.
2. **Tạo / xoá node chỉ qua camera** (`PATCH /cameras/update_camera` với `observedNodeIds` là
   *tập đích*). Bỏ id khỏi list = **xoá node + ROI + mọi pair chứa node** (cascade).
3. **Zone của node = zone của camera.** Đổi zone phải đổi trên camera.
4. **Pair cần cả 2 node đã có ROI.** Pair được phép xuyên zone (runtime chỉ log warning).
5. **Start mới bắt buộc có priority**, unique trong zone (`409` nếu trùng).
6. **Mọi API ghi cấu hình cần inference đang pause** → nếu đang chạy trả `409`
   (`require_inference_paused` trong `application/fe_api/sync_rules.py`).
7. **Runtime đọc cấu hình 1 lần lúc start.** Đổi priority / pair / camera trong Mongo chỉ có
   hiệu lực sau `POST /api/v1/runtime/reload` (hoặc restart).

---

## 3. Vòng đời một node trong RAM (`domain/node_state.py`)

Mỗi node có 3 thông tin độc lập: `detected`, `isReady`, `lock {user, system, orderId}`.

| Loại node | Khi nào `isReady` | Ý nghĩa |
|-----------|-------------------|---------|
| `start_*` | **Có hàng** liên tục > `START_READY_AFTER_SEC` và không bị lock | Có hàng để lấy |
| `end_*` | **Trống** liên tục > `END_READY_AFTER_SEC` và không bị lock | Có chỗ để đặt |

> Bẫy hay gặp: **end ready khi TRỐNG**, ngược với start.

- Mỗi lần `detected` đổi giá trị, bộ đếm thời gian của node reset về 0.
- `process_starts()` / `process_ends()` chạy mỗi ~1s trong thread PairManager để đưa node vào ready.
- Gửi ICS thành công → `set_pair_used()`: **cả start và end** bị `lock.system = true` + `orderId`,
  bị gỡ khỏi ready.
- **Hệ thống KHÔNG tự gỡ `lock.system` theo thời gian.** Chỉ gỡ bằng webhook ICS (status 3/23)
  hoặc operator `POST /nodes/unlock_by_user`.
- Gỡ lock xong → node phải chờ lại đủ timer mới ready lại.
- Lock được ghi Mongo và **hydrate lại khi runtime khởi động** (`runtime_service.start`).
- Timer mặc định 10s (`domain/settings.py`), giá trị chạy thật lấy từ `config/settings.py` / `.env`.

---

## 4. Luồng một ca vận hành

| # | Operator làm | API | Bên trong |
|---|--------------|-----|-----------|
| 1 | Bật camera + AI | `POST /api/v1/system/start-cameras` | Bật mọi camera, chờ model + ≥1 camera có frame, **resume inference** (`StartCameras`) |
| 2 | Đẩy hàng vào ô, chờ | SSE `GET /runtime/events` hoặc `GET /runtime/get_pending_pairs` | Start dần chuyển `isReady` |
| 3 | Bấm gửi robot | `POST /api/v1/runtime/dispatch` | `ConfirmDispatch` chốt batch theo luật head/tail (mục 5), **mở gate** |
| 4 | Theo dõi | `GET /runtime/get_pending_pairs`, SSE `GET /dispatch/events` | PairManager mỗi 1s gửi tối đa **1 lệnh / zone** |
| 5 | Robot chạy | ICS gọi `POST /api/v1/external_server/unlock_by_order_status` | `6` → panel "inprogress"; `3`/`23` → gỡ `lock.system` cặp start/end, xoá khỏi panel |
| 6 | Hết batch | — | Gate tự đóng (`stopReason = batch_complete`), **inference vẫn chạy** → quay lại bước 2 |

Thao tác phụ:
- `POST /runtime/cancel-batch` — đóng gate, inference vẫn chạy. Lệnh đã gửi ICS **không** bị huỷ.
- `POST /runtime/pause-scan` — dừng inference **và** huỷ batch. Bắt buộc trước khi sửa cấu hình.
- `POST /runtime/reload` — nạp lại camera/pair/priority từ Mongo (mất batch đang chạy).

Route cũ còn giữ làm alias (deprecated, có header `X-Use-Instead`):
`/system/start_all` (chỉ bật camera, không bật AI), `/runtime/start-scan`, `/runtime/confirm-dispatch`.

---

## 5. Luật batch — phần dễ sai nhất (`domain/batch_policy.py`)

### 5.1 Lúc bấm Dispatch: lấp head → tail theo từng col (`fill_cols_head_to_tail`)

Trong mỗi col, các start xếp theo priority tăng dần (lối vào → sâu).
- **Head** = start `isReady` có priority nhỏ nhất; **tail** = start `isReady` priority lớn nhất.
- Mọi start từ head tới tail đều vào batch, **kể cả không ready** (giả định: hai đầu có hàng
  thì ở giữa cũng có — camera có thể bị che). Các start này gọi là **filled**.
- Gặp start bị lock (user hoặc system) giữa head → tail: **dừng**, phần sau không vào batch.
- Có `lock.user` **trước** head → bỏ **cả col**. `lock.system` trước head → không chặn.
- Chỉ start có pair normal `(start, end)` mới tính (`dispatchable_starts`).

Ví dụ col A, priority 1→5, ready = {2, 4}:

```
priority:   1     2      3      4      5
ready:      -     ✔      -      ✔      -
batch:            ✔      ✔(fill) ✔            → batch = {2, 3, 4}, filled = {3}
nếu 3 có lock.system:    ✔  ✗dừng             → batch = {2}
nếu 1 có lock.user:      cả col bị bỏ          → batch = {}
```

Từ chối Dispatch (`409`) khi: inference đang pause, batch trước chưa xong, chưa có start ready,
hoặc mọi col đều bị `lock.user` chặn.

### 5.2 Mỗi vòng gửi: head "tiếp cận được" theo kiểu ngăn xếp (`plan_col_dispatch`)

- Robot chỉ lấy được start X khi **mọi start phía trước X trong col đều không còn chờ**
  (đã gửi, hoặc vốn không có trong batch).
- Mỗi zone: duyệt col theo `col_id` tăng dần (A < B < C), lấy head tiếp cận được của col đầu tiên
  → **chỉ cho phép 1 start / zone / vòng**.
- Zone có bất kỳ start nào đang `lock.system` → **chờ** (đưa vào `waitingFor`), không gửi gì.
  Hệ quả: trong một zone các lệnh chạy **tuần tự**, lệnh sau chỉ đi khi ICS báo 3/23 cho lệnh trước.
- Các zone khác nhau chạy **song song**.
- **Trust**: start trong batch được gửi kể cả khi đã mất `isReady` (`DispatchGate.trusted_starts`).
- Start `isReady` mới xuất hiện **ngoài batch** không làm dừng gì — chỉ báo trong
  `newNodesOutsideBatch`, chờ lần Dispatch sau.
- Mỗi start chỉ gửi **1 lần** trong batch. Gửi hết (`remaining = 0`) → gate đóng.

### 5.3 Ghép start → end (`domain/dispatch/pairing.py`)

`build_dispatch_pairs`: sort start theo `(priority, zone_id, node_id)`, với mỗi start lấy **end đầu
tiên** trong danh sách pair mà end đó đang `isReady` và chưa bị dùng trong vòng này.
Không có end ready → start đó chờ (xuất hiện trong `get_pending_pairs`, không có trong `nextPairs`).

---

## 6. Gửi ICS và nhận webhook

**Gửi** (`application/dispatch/dispatch_service.py` → `dispatch_single`):
1. Chụp frame start/end (nếu `ENABLE_SNAPSHOTS`) **trước** khi gửi.
2. Payload (`application/dispatch/ics_payload.py`):
   `orderId = "S-{số start}-{số end}-{datetime}"`, `modelProcessCode = ICS_PROCESS_SINGLE`,
   `taskPath = "{số start},{số end}"` (số = chữ số trong node id).
3. `HttpDispatchGateway` POST `ICS_URL`, retry `ICS_RETRY_TIMES`.
4. Thành công → ghi ảnh snapshot, `set_pair_used` (lock.system), thêm vào panel active task
   ("issued"), `OnDispatchSuccess` ghi nhận vào batch. Mọi lần gửi (OK/fail) đều vào `dispatch_logs`.

**Webhook ICS** (`UnlockByOrderStatus` trong `application/dispatch/active_tasks.py`), không cần token:

| Status ICS | Hành vi |
|------------|---------|
| `6` Running | Panel → `inprogress` |
| `9` Assigned | Panel → `issued` |
| `3` Canceled, `23` Placed | Gỡ `lock.system` của cặp + xoá khỏi panel |
| Khác | Bỏ qua, vẫn `200` |

Mã status định nghĩa ở `domain/models.py` `OrderStatus`. Sau restart, RAM mất `order_mapping`
nhưng vẫn gỡ được lock nhờ `lock.orderId` đã hydrate từ Mongo (`ResetFlagsByOrder`).

---

## 7. Quyền (`domain/permissions.py`)

FE và backend kiểm tra theo **mảng `permissions`** trong token, **không theo tên role**.
Role chỉ dùng lúc seed user để gán bộ quyền mặc định (`ROLE_PERMISSIONS`).

| Quyền | Dùng cho |
|-------|----------|
| `system.control` | start-cameras, dispatch, cancel/pause, reload, stop |
| `camera.write` | Camera, ROI, gán node |
| `pair.write` | CRUD pair |
| `node.maintenance` | set_maintenance, set_lock, unlock_by_user |
| `*.read`, `logs.read`, `map.*` | Đọc tương ứng |

Route gắn quyền bằng `Depends(require_permission(...))` (`presentation/deps.py`).

---

## 8. Kiến trúc tầng — đặt code ở đâu

| Tầng | Thư mục | Được làm | Không được |
|------|---------|----------|-----------|
| Domain | `domain/` | Luật nghiệp vụ thuần Python, hàm thuần | Import fastapi, torch, motor, `config` |
| Application | `application/` | Use case: điều phối domain + port | Gọi trực tiếp Mongo/HTTP (đi qua `ports.py`) |
| Infrastructure | `infrastructure/` | Mongo, GPU, ICS HTTP, thread loop | Chứa luật nghiệp vụ |
| Presentation | `presentation/routes/v1/` | Route mỏng: auth + gọi `container.<use_case>` | Logic |
| Wiring | `application/container.py`, `application/runtime/runtime_service.py`, `app.py` | Nối mọi thứ | — |

`tests/domain/test_layer_boundaries.py` tự fail nếu `domain/` import sai.

---

## 9. Muốn thay đổi X thì sửa file nào

| Muốn đổi | Sửa chính | Đi kèm / test |
|----------|-----------|---------------|
| Thời gian chờ để start/end ready | `.env` → `START_READY_AFTER_SEC`, `END_READY_AFTER_SEC` | Default test: `domain/settings.py` |
| Ngưỡng "có hàng" (confidence, % che ROI) | `.env` → `THRESHOLD_DETECT`, `THRESHOLD_COVERAGE` | Logic: `infrastructure/vision/detection.py` |
| Class YOLO nào tính là hàng (đang `cls == 0`) | `infrastructure/vision/detection.py` | Model: `MODEL_PATH`, `scripts/export_engine.py` |
| Điều kiện ready / lock / gỡ lock của node | `domain/node_state.py` | `tests/domain/test_node_state.py` |
| Luật chốt batch (head/tail, lock chặn col) | `domain/batch_policy.py` `fill_cols_head_to_tail`, `_fill_one_col` | `application/cameras/confirm_dispatch.py`, `tests/domain/test_batch_fill_head_tail.py` |
| Thứ tự gửi trong zone / col, số lệnh song song mỗi zone | `domain/batch_policy.py` `plan_col_dispatch`, `col_head_in_zone`, `busy_zones` | `application/dispatch/dispatch_gate.py`, `tests/domain/test_batch_policy_cols.py`, `tests/application/test_dispatch_gate.py` |
| Cách sort priority / thứ tự col | `domain/dispatch/priority.py` (`start_sort_key`, `col_sort_key`) | Priority unique trong zone: `application/fe_api/priority_rules.py` |
| Chọn end nào cho một start | `domain/dispatch/pairing.py` | `tests/domain/test_dispatch.py` |
| Khi nào batch tự đóng | `domain/batch_policy.py` `should_auto_pause` | `application/cameras/on_dispatch_success.py` |
| Nội dung payload gửi ICS / format `orderId` | `application/dispatch/ics_payload.py` + `.env` `ICS_PROCESS_*` | Nếu đổi format `orderId` → sửa luôn `domain/dispatch/active_task.py` `parse_order_id` |
| URL / retry ICS | `.env` `ICS_URL`, `ICS_RETRY_*`, `ICS_ORDER_LIST_URL`, `ICS_AREA_ID` | `infrastructure/ics/` |
| Ý nghĩa mã status ICS (3/6/9/23) | `domain/models.py` `OrderStatus` | `domain/reset_policy.py`, `domain/dispatch/active_task.py`, `application/dispatch/active_tasks.py` |
| Bật strategy Empty / Double | `application/runtime/runtime_service.py` (đang bind `SingleDispatch`) | Đọc mục 1 của [pending-tasks.md](./pending-tasks.md) trước — còn bug |
| Luật cascade camera → node → pair | `application/fe_api/sync_rules.py` | `cameras_update.py`, `cameras_crud.py`, `rois.py`, `pairs.py`, `tests/application/test_fe_api.py` |
| Cho phép sửa cấu hình khi inference đang chạy | `application/fe_api/sync_rules.py` `require_inference_paused` | Cẩn thận: runtime chỉ nạp cấu hình lúc start |
| Quyền / role mặc định | `domain/permissions.py` | `scripts/seed_users.py` chạy lại để sync user cũ; `tests/domain/test_permissions.py` |
| Thêm API mới | Use case `application/...` → bind `application/container.py` → route `presentation/routes/v1/` | Mount router mới trong `app.py`; test với `tests/application/fakes.py` |
| Field node đẩy qua SSE | `domain/node_state.py` `snapshot_points` | `application/runtime/runtime_state_hub.py` `map_runtime_item` |
| Ảnh snapshot khi dispatch | `infrastructure/storage/snapshot_fs.py` | `.env` `ENABLE_SNAPSHOTS`, `SNAPSHOT_DIR` |
| Kích thước batch GPU / số stream | `.env` `INFERENCE_*` | Phải khớp engine export (`scripts/export_engine.py`) |

Quy trình an toàn khi đổi luật nghiệp vụ:
1. Sửa hàm thuần trong `domain/` trước, viết test domain (chạy không cần GPU/Mongo):
   `uv run --extra dev pytest tests/domain -q`.
2. Chạy test application: `uv run --extra dev pytest tests/application -q`.
3. Thử end-to-end bằng **sandbox** (camera/AI/ICS giả, FE bật/tắt hàng từng ô):
   `.env` `RUNTIME_MODE=sandbox` + `MONGODB_DB=..._sandbox`, seed `scripts/seed_sandbox.py`.
   Contract: [fe-api-sandbox.md](./fe-api-sandbox.md).
4. Dùng `uv run` (Python 3.10 + đủ thư viện) — **không** dùng Python hệ thống để verify.

---

## 10. Bẫy đã gặp

- **Đổi priority/pair trong Mongo mà không reload** → runtime vẫn chạy theo bản cũ.
- **Hai file settings**: `domain/settings.py` chỉ là default cho test; giá trị thật là
  `config/settings.py` + `.env`. Không import `config` trong `domain/`.
- **End ready khi trống** — đọc ngược là sai toàn bộ ghép cặp.
- **`flag` ≠ một loại lock riêng**: `flag = lock.user OR lock.system`, chỉ còn để tương thích.
- **Maintenance không chặn dispatch lâu dài** và **lock.user bật sau khi confirm không chặn start
  trong batch** — xem mục 1 [pending-tasks.md](./pending-tasks.md) trước khi hứa với vận hành.
- **Runtime start lỗi không làm sập app**: CRUD/auth vẫn chạy, `get_health` trả `503`; sửa xong gọi
  `POST /runtime/reload`.

## 11. Tài liệu liên quan

- Vận hành ca: [runbook-runtime-product.md](./runbook-runtime-product.md)
- Contract dispatch cho FE: [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md)
- Webhook ICS + panel lệnh: [fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md), [fe-api-active-tasks.md](./fe-api-active-tasks.md)
- Cấu hình camera/node/pair: [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md), [fe-api-start-priority.md](./fe-api-start-priority.md)
- Response / status code mọi API: [fe-api-responses-status.md](./fe-api-responses-status.md)
