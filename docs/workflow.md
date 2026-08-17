# Workflow Chi Tiết — AMR Camera Dispatch System

---

## Tổng quan luồng chính

```
STARTUP → START CAMERAS → LOADING → [confirm-ready] → SCANNING → DISPATCH → WAITING → [auto-pause / next batch]
```

---

## Phase 1: STARTUP — Khởi động hệ thống

**Trigger:** `uvicorn app:app` hoặc `python main.py`

**File:** `app.py` → `lifespan()`

```
app.py::lifespan()
  │
  ├── 1. connect MongoDB
  │     repository/db.py::connect(MONGODB_URL, MONGODB_DB)
  │     → Tạo AsyncIOMotorClient duy nhất cho toàn app
  │
  └── 2. runtime_service.start()
        service/runtime_service.py::start()
          │
          ├── 2a. _load_configs()
          │     ├── camera_repository.get_by_zone()
          │     │     → List[Dict] chứa url, rois, zone_id, enabled
          │     └── pairs_repository.get_as_tuples()
          │           → [(start_1, end_1), (start_2, end_2), (start_empty,), ...]
          │           → Fallback: config/pairs.py nếu DB trống
          │
          ├── 2b. _init_state(pairs)
          │     core/state_manager.py::StateManager(validate_pairs)
          │     → points = defaultdict (tất cả nodes)
          │     → ready_start_list = set()
          │     → ready_end_list   = set()
          │     → order_mapping    = {}
          │
          ├── 2c. _init_components(sm, cameras, pairs)
          │     ├── SnapshotManager (nếu ENABLE_SNAPSHOTS=True)
          │     ├── PairManager + inject SingleDispatch
          │     │     → PairManager._run() thread start
          │     ├── InferenceEngine (initial_paused=True)
          │     │     → Load model từ MODEL_PATH
          │     │     → Tạo CUDA streams (num_streams=3)
          │     │     → _paused=True → chưa xử lý frame
          │     └── CameraManager
          │           → enabled = [False] * N ← tất cả disabled
          │           → Tạo N CameraProcessor threads
          │           → Mỗi thread: chờ enabled=True
          │
          └── 2d. _inject_services(components)
                camera_service.attach(cam_mgr, inference_eng, sm)
                state_service.attach(sm)
                node_service.attach(sm)
```

**Trạng thái sau startup:**
```
InferenceEngine:  PAUSED    ← chưa xử lý frame
CameraProcessors: RUNNING   ← threads đang chạy, chờ enabled=True
PairManager:      RUNNING   ← loop đang chạy, không có pairs
```

---

## Phase 2: START CAMERAS — Kết nối RTSP

**Trigger:** Operator gọi `POST /cameras/start-all`

**File:** `presentation/routes/cameras.py` → `service/camera_service.py`

```
POST /cameras/start-all
  │
  └── camera_service.start_all()
        │
        ├── camera_manager.start_all_cameras()
        │     → enabled[0..N] = True
        │     → CameraProcessor threads bắt đầu đọc RTSP
        │         core/gpu_video_decoder.py
        │         → FFmpeg NVDEC decode frame
        │         → frame: numpy array (H, W, 3)
        │
        └── KHÔNG resume inference_engine ← phải chờ confirm-ready
```

**Trạng thái sau start-all:**
```
CameraProcessors: READING RTSP  ← đang đọc frame
InferenceEngine:  PAUSED        ← vẫn chưa xử lý
```

---

## Phase 3: LOADING — Operator đẩy hàng vào kho

**Không có code nào chạy — đây là thao tác vật lý.**

Operator đẩy hàng vào các ô start trên sàn kho.

**API có thể gọi trong giai đoạn này:**
```
GET /runtime/status         → xem hệ thống đang running chưa
GET /nodes/zone/{zone_id}   → xem danh sách nodes
GET /cameras/status         → xem cameras connected chưa, batch info
```

---

## Phase 4: CONFIRM READY — Bắt đầu scan batch mới

**Trigger:** Operator gọi `POST /runtime/confirm-ready`

**File:** `presentation/routes/runtime.py` → `service/camera_service.py`

```
POST /runtime/confirm-ready
  │
  └── camera_service.confirm_ready()
        │
        ├── Guard: cameras.enabled == 0?
        │     → YES: return error "Call /cameras/start-all first"
        │     → NO:  tiếp tục
        │
        ├── Snapshot nodes đang detected
        │     _get_current_detected_nodes()
        │     → Lấy tất cả start_ nodes có state=True từ state_manager
        │     → snapshot_nodes = {start_A1, start_A2, start_B1, ...}
        │     → batch_size     = len(snapshot_nodes)
        │
        ├── Reset batch counters
        │     sum_request  = 0
        │     batch_active = True
        │
        └── inference_engine.resume()
              → _paused.clear()
              → InferenceEngine bắt đầu xử lý frames
```

**Response:**
```json
{
    "success": true,
    "snapshot_size": 4,
    "snapshot_nodes": ["start_A1", "start_A2", "start_B1", "start_C3"]
}
```

---

## Phase 5: SCANNING — Camera quét và voting

**Chạy liên tục sau confirm-ready — vòng lặp chính của hệ thống.**

### 5a. Camera đọc frame

**File:** `core/camera_processor.py::run()`

```
CameraProcessor.run() [loop]
  │
  ├── Kiểm tra enabled_ref[camera_index]
  │     → False: sleep(1), bỏ qua
  │     → True: tiếp tục
  │
  ├── GPUVideoDecoder.read_frame()
  │     core/gpu_video_decoder.py
  │     → FFmpeg NVDEC decode frame trên GPU
  │     → frame: numpy array (H, W, 3) trên CPU RAM
  │
  ├── inference_engine.put_frame_with_drop(frame, cam_id)
  │     → Đẩy frame vào shared_queue
  │     → Nếu queue full: drop oldest frame (tránh lag)
  │
  └── result_queue.get(timeout=0.1)
        → Chờ kết quả detection từ InferenceEngine
        → Nhận detections: torch.Tensor (N, 6) [x1,y1,x2,y2,conf,cls]
```

### 5b. Inference Engine xử lý batch

**File:** `core/inference_engine.py::run()`

```
InferenceEngine.run() [loop]
  │
  ├── Kiểm tra _paused.is_set()
  │     → True: sleep, bỏ qua
  │     → False: tiếp tục
  │
  ├── _collect_batch()
  │     → Gom frames từ shared_queue
  │     → Tối đa max_batch_size=32 frames hoặc batch_timeout=1.0s
  │
  ├── model.predict(batch_frames)
  │     → YOLO inference trên GPU (CUDA streams)
  │     → Output: List[torch.Tensor]
  │     → Mỗi tensor shape (N, 6): [x1, y1, x2, y2, conf, cls]
  │
  └── Phân phối kết quả về đúng camera
        result_queues[cam_id].put(detections)
```

### 5c. Detection theo từng ROI

**File:** `core/detection.py::has_object_in_roi()`

```
Với mỗi roi_dict trong self.rois:
  │
  ├── node_id = "start_10001050"
  ├── roi     = [x, y, w, h]
  │
  └── has_object_in_roi(detections, roi, use_gpu=True)
        │
        ├── Lọc: cls==0 AND conf > THRESHOLD_DETECT(0.4)
        │
        ├── calculate_coverage_batch(detections, roi, device='cuda')
        │     utils/overlap_utils.py
        │     → % diện tích overlap box vs ROI (GPU tensor)
        │
        └── max_coverage >= THRESHOLD_COVERAGE(0.5)?
              → True:  has_object=True
              → False: has_object=False
```

### 5d. Voting logic

**File:** `core/state_manager.py::get_state_nodes()`

```
state_manager.get_state_nodes(node_id, has_object)
  │
  ├── State THAY ĐỔI (old != new):
  │     → Reset timer: points[node_id]["time"] = now()
  │     → start node mất hàng → discard khỏi ready_start_list
  │     → end node có hàng    → discard khỏi ready_end_list
  │
  └── State KHÔNG ĐỔI:
        → Timer tiếp tục tăng (không reset)
```

---

## Phase 6: PAIR READY — Node đủ điều kiện

**Chạy trong PairManager thread, mỗi 1 giây.**

**File:** `core/pair_manager.py::_run()`

```
PairManager._run() [loop mỗi 1s]
  │
  ├── state_manager.process_starts()
  │     → start node: state=True AND flag=False AND existed_time > 30s?
  │         → YES: ready_start_list.add(node_id)
  │
  ├── state_manager.process_ends()
  │     → end node: state=False AND flag=False AND existed_time > 60s?
  │         → YES: ready_end_list.add(node_id)
  │
  └── make_pairs()
        ├── Sort ready_start_list theo priority (số nhỏ = ưu tiên cao)
        │     sorted_starts = sorted(ready_start_list, key=get_node_priority)
        │
        └── Với mỗi start theo priority:
              → Tìm end trong validate_pairs
              → end phải có trong ready_end_list và chưa được dùng
              → Return: pairs = [(start_1,end_1), (start_2,end_2), ...]
```

---

## Phase 7: DISPATCH — Gửi lệnh cho AMR

**File:** `core/pair_manager.py::SingleDispatch.execute()`

```
SingleDispatch.execute(pairs, ...)
  │
  └── Với mỗi (start_point, end_point) trong pairs:
        │
        ├── payload_sent_ICS(start_point, end_point)
        │     utils/data.py
        │     → {"orderId": "S-{start}-{end}-{datetime}", ...}
        │
        ├── post(payload) — retry 3 lần, delay 1s
        │     → POST {ICS_URL} timeout=5s
        │     → response["code"] == 1000? → success
        │
        ├── Nếu SUCCESS:
        │     ├── state_manager.set_pair_used(start, end, order_id)
        │     │     → flag[start] = True, flag[end] = True
        │     │     → discard khỏi ready lists
        │     │     → order_mapping[order_id] = [(start, end, False)]
        │     │
        │     └── camera_service.on_dispatch_success(start_point)
        │           → sum_request += 1
        │           → remaining = snapshot_size - sum_request
        │           │
        │           ├── remaining == 0?
        │           │     → AUTO PAUSE: inference_engine.pause()
        │           │     → reset_batch()
        │           │     → log "Batch complete — ready for next load"
        │           │
        │           └── remaining > 0?
        │                 → _check_new_nodes()
        │                 → current_detected - snapshot_nodes = new_nodes?
        │                     → YES: WARNING + PAUSE (hàng mới đẩy vào)
        │                     → NO:  tiếp tục chờ
        │
        └── Nếu FAILED sau 3 lần:
              logger.error(...)  ← log lỗi, không retry thêm
```

---

## Phase 8: WAITING — Chờ AMR hoàn thành

**Cặp A-B bị LOCKED — flag=True cho cả start và end.**

```
AMR nhận lệnh → lấy hàng tại start → đặt hàng tại end → báo RCS
  │
  └── RCS gọi webhook:
        POST /delete-flag
        Body: {"orderId": "S-...", "status": 23}
          │
          └── state_service.reset_flags_by_order(order_id, status)
                │
                ├── status=3  → reset ALL pairs của order
                │     → flag[start] = False, flag[end] = False
                │     → del order_mapping[order_id]
                │
                └── status=23 → reset chỉ EMPTY pairs
                      → Giữ nguyên normal pairs
```

---

## Phase 9: AUTO PAUSE / NEXT BATCH

### Case 1: Batch hoàn thành bình thường

```
sum_request == snapshot_size
  → inference_engine.pause()    ← AUTO PAUSE
  → reset_batch()
  → Operator đẩy hàng lần 2
  → POST /runtime/confirm-ready ← bắt đầu batch mới
```

### Case 2: Phát hiện hàng mới trong khi đang dispatch

```
current_detected - snapshot_nodes = {new_node}
  → WARNING log: "New nodes detected"
  → inference_engine.pause()    ← SAFETY PAUSE
  → reset_batch()
  → Operator nhận cảnh báo
  → Gọi POST /runtime/pause-scan (thủ công nếu cần)
  → Sau khi an toàn → POST /runtime/confirm-ready lại
```

### Case 3: Operator pause thủ công

```
POST /runtime/pause-scan
  → camera_service.pause_scan()
  → inference_engine.pause()
  → reset_batch()
```

---

## Sơ đồ luồng tổng thể

```
STARTUP
  └── load DB → init components → inject services
        ↓
POST /cameras/start-all
  └── enable cameras → connect RTSP
        ↓
LOADING (vật lý)
  └── operator đẩy hàng vào ô
        ↓
POST /runtime/confirm-ready
  └── snapshot detected nodes (batch_size=N)
  └── inference_engine.resume()
        ↓
SCANNING [loop liên tục]
  ┌──────────────────────────────────────────────┐
  │  Camera → frame → InferenceEngine (batch)    │
  │    → detections (GPU Tensor)                 │
  │    → has_object_in_roi() cho mỗi ROI         │
  │    → state_manager.get_state_nodes()         │
  └──────────────────────────────────────────────┘
        ↓
PAIR READY [PairManager loop mỗi 1s]
  ┌──────────────────────────────────────────────┐
  │  process_starts(): start 30s → ready         │
  │  process_ends():   end 60s   → ready         │
  │  make_pairs(): sort priority → ghép cặp      │
  └──────────────────────────────────────────────┘
        ↓
DISPATCH
  └── SingleDispatch → POST ICS → flag=True
  └── on_dispatch_success() → sum_request += 1
        ↓
  ┌─────────────────────────────────────────────────────┐
  │  remaining == 0?  → AUTO PAUSE → next batch         │
  │  new node found?  → WARNING + SAFETY PAUSE          │
  │  dispatch failed? → log error, remaining unchanged  │
  └─────────────────────────────────────────────────────┘
        ↓
WAITING
  └── AMR → RCS → POST /delete-flag → reset flags
        ↓
  └── quay lại SCANNING ↑
```

---

## Trạng thái của 1 node

```
Node start:
  state=False, flag=False              → Ô TRỐNG
  state=True,  flag=False              → CÓ HÀNG, đếm thời gian
  state=True,  flag=False, time > 30s  → VÀO ready_start_list
  state=True,  flag=True               → ĐANG DISPATCH (locked)
  state=False, flag=False              → Robot đã lấy xong

Node end:
  state=True,  flag=False              → ĐẦY, không nhận
  state=False, flag=False              → TRỐNG, đếm thời gian
  state=False, flag=False, time > 60s  → VÀO ready_end_list
  state=False, flag=True               → ĐANG NHẬN HÀNG (locked)
  state=True,  flag=False              → Robot đã đặt xong
```

---

## Batch tracking state

```
Sau confirm_ready():
  snapshot_nodes = {A1, A2, B1, C3}   ← chụp lúc confirm
  sum_request    = 0
  batch_active   = True

Sau mỗi dispatch thành công:
  sum_request += 1
  remaining = len(snapshot_nodes) - sum_request

  remaining == 0 → AUTO PAUSE
  remaining > 0  → check new nodes → WARNING nếu có node mới
```

---

## Thread map

```
Main thread:      FastAPI event loop (async)
InferenceEngine:  1 thread — batch inference GPU
CameraProcessor:  N threads — 1 thread/camera
PairManager:      1 thread — dispatch loop mỗi 1s
SnapshotManager:  1 thread (nếu ENABLE_SNAPSHOTS=True)
```

---

## Service ownership

```
runtime_service   → lifecycle (start/stop/reload)
camera_service    → camera control + scanning lifecycle (confirm_ready, pause_scan, batch tracking)
state_service     → flag management, webhook handler
node_service      → node enable/disable, priority
pairs_service     → pairs CRUD
```
