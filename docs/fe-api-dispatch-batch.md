# Contract FE — Scan & dispatch theo batch

> Cập nhật: 2026-11-10 (luật head/tail theo col, gộp start-cameras, đổi tên `/dispatch`)  
> Liên quan: [fe-api-sandbox.md](./fe-api-sandbox.md), [fe-api-active-tasks.md](./fe-api-active-tasks.md)  
> Giải thích nghiệp vụ đầy đủ: [onboarding-business-logic.md](./onboarding-business-logic.md) mục 4–5.

Prefix: `/api/v1`. Auth Bearer. Lỗi trả `{ "message": "..." }`.

| Bước | API | Làm gì |
|------|-----|--------|
| Bật camera + AI | `POST /system/start-cameras` | Bật mọi camera, chờ ≥1 camera có frame, **resume inference**. Chưa gửi ICS |
| Gửi robot | `POST /runtime/dispatch` | Chụp **batch** theo col → mở cổng gửi ICS |

Alias deprecated (vẫn chạy, header `X-Deprecated` / `X-Use-Instead`):
`POST /system/start_all` (chỉ bật camera, **không** bật inference), `POST /runtime/start-scan`,
`POST /runtime/confirm-dispatch` (= `/runtime/dispatch`).

**Thuật ngữ**
- **Batch**: các start được phép gửi ICS trong 1 lần xác nhận. Chụp lúc bấm Dispatch, không đổi sau đó.
- **Cổng gửi (gate)**: mở = BE được gửi lệnh cho start trong batch; đóng = không gửi gì.
- **`isReady`**: start có hàng ổn định ≥ `START_READY_AFTER_SEC`.
- **Col**: làn trong zone (`col_id`). Robot vào từ start có priority nhỏ nhất.
- **Filled**: start không `isReady` nhưng được đưa vào batch vì nằm giữa head và tail của col.

---

## Luồng nghiệp vụ

```
start-cameras ──► (đẩy hàng, chờ isReady) ──► dispatch ──► BE gửi 1 lệnh / zone, tuần tự trong zone
                         ▲                                         │
                         └──── cổng đóng (batch_complete / canceled) ◄┘
```

1. `POST /system/start-cameras` — camera + inference chạy. FE thấy `detected` / `isReady` qua SSE `node.runtime`.
2. Đẩy hàng. Xem trước bằng `GET /runtime/get_pending_pairs`.
3. `POST /runtime/dispatch` — chốt batch, BE bắt đầu gửi.
4. Cổng tự đóng khi gửi hết batch (`batch_complete`). Inference **vẫn chạy** → quay lại bước 2.
5. Batch kẹt → `POST /runtime/cancel-batch` (inference vẫn chạy).
6. Sửa cấu hình → `POST /runtime/pause-scan` (dừng inference **và** huỷ batch). Chạy lại: `start-cameras`.

### Luật chốt batch (lúc bấm Dispatch)

Trong mỗi col (start sort priority tăng dần):
- Head = start `isReady` priority nhỏ nhất; tail = start `isReady` priority lớn nhất.
- Mọi start từ head → tail vào batch, **kể cả không ready** (→ `filledNodes`).
- Gặp start có lock (user/system) giữa head → tail: dừng, phần sau không vào batch.
- `lock.user` nằm trước head → bỏ cả col. `lock.system` trước head → không chặn.
- Chỉ start có pair normal (start → end) mới tính. `start_empty` không tính.

### Luật gửi (mỗi giây)

- Start X chỉ gửi được khi mọi start phía trước X (priority nhỏ hơn, cùng col) đều không còn chờ trong batch.
- Mỗi zone: duyệt col theo `col_id` tăng dần, gửi **tối đa 1 start / zone**.
- Zone đang có start `lock.system` (lệnh trước chưa được ICS báo 3/23) → chờ, hiện trong `waitingFor`.
- Start trong batch được gửi **kể cả khi đã mất `isReady`** (trust). Mỗi start tối đa 1 lần.
- Start `isReady` mới **ngoài batch** không làm dừng — chỉ báo trong `newNodesOutsideBatch`, chờ Dispatch lần sau.

---

## `POST /system/start-cameras`

Quyền `system.control`. Body rỗng.

```json
{
  "message": "Cameras started and scanning",
  "total": 4, "enabled": 4, "streaming": 3,
  "cameras": [ ... ],
  "warnings": ["2: not streaming yet"],
  "scanning": true
}
```

| HTTP | Khi nào |
|------|---------|
| `200` | Model đã load và ≥1 camera có frame (camera lỗi nằm trong `warnings`) |
| `503` | Runtime chưa sẵn / model không load / không camera nào stream |

---

## `POST /runtime/dispatch`

Quyền `system.control`. Body rỗng.

```json
{
  "message": "Dispatch confirmed",
  "batchSize": 3,
  "batchNodes": ["start_9000001", "start_9000002", "start_9000003"],
  "filledNodes": ["start_9000002"]
}
```

`batchNodes` sort theo (priority, zone, nodeId). Thứ tự gửi thật theo luật col/zone ở trên.

| HTTP | `message` | FE xử lý |
|------|-----------|----------|
| `200` | — | Hiển thị batch, disable nút tới khi cổng đóng |
| `400` | `System not initialized` | Runtime chưa sẵn |
| `409` | `Inference đang pause — ...` | Gọi `start-cameras` trước |
| `409` | `Batch trước chưa xong — ...` | Chờ cổng đóng, hoặc `cancel-batch` / `pause-scan` |
| `409` | `Chưa có start isReady — ...` | Chờ hàng được nhận diện ổn định |
| `409` | `Các col có start ready đều bị chặn bởi lock_user phía trước` | Gỡ lock.user ở đầu col |

---

## `GET /runtime/get_pending_pairs`

Chỉ cần đăng nhập. Không side-effect (poll 1–2s).

```json
{
  "runtimeReady": true,
  "batch": {
    "active": true,
    "size": 3,
    "nodes": ["start_9000001", "start_9000002", "start_9000003"],
    "filled": ["start_9000002"],
    "dispatched": ["start_9000001"],
    "skipped": [],
    "remaining": 2,
    "stopReason": null,
    "newNodes": []
  },
  "readyStarts": [
    { "nodeId": "start_9000003", "priority": 3, "nodeName": "A-03", "zoneId": "SBA", "colId": "A",
      "inBatch": true, "dispatched": false, "skipped": false }
  ],
  "nextPairs": [],
  "waitingFor": [
    { "zoneId": "SBA", "colId": "A", "nodeId": "start_9000002", "reason": "zone_locked" }
  ],
  "filledNodes": ["start_9000002"],
  "stuckNodes": [],
  "colStatus": [
    { "zoneId": "SBA", "colId": "A", "headNodeId": "start_9000002", "headInBatch": true }
  ],
  "newNodesOutsideBatch": []
}
```

| Field | Ý nghĩa |
|-------|---------|
| `batch.active` | `true` = cổng mở |
| `batch.nodes` / `filled` / `dispatched` / `remaining` | Batch hiện tại, start được lấp, đã gửi, còn lại |
| `batch.stopReason` | `null` / `batch_complete` / `canceled` |
| `readyStarts` | Start đang `isReady` (có pair normal), sort priority |
| `nextPairs` | Cặp sẽ gửi ở vòng kế (đã lọc luật col/zone) |
| `waitingFor` | Head của zone đang chờ vì zone còn lệnh chưa xong (`reason: zone_locked`) |
| `filledNodes` | Start được lấp head→tail còn chờ gửi — bình thường, không phải lỗi |
| `stuckNodes` | Start trong batch, không ready, không phải filled — nghi mất hàng (BE vẫn gửi) |
| `colStatus` | Head hiện tại của từng col |
| `newNodesOutsideBatch` | Start ready ngoài batch — chờ Dispatch lần sau |

`nextPairs` rỗng dù batch mở → thường do end chưa `isReady`, hoặc zone đang chờ (`waitingFor`).

Runtime chưa sẵn → `200` với `runtimeReady: false`, các list rỗng.

---

## `POST /runtime/cancel-batch`

Quyền `system.control`. **Chỉ đóng cổng** — inference vẫn chạy.

```json
{ "message": "Batch canceled", "dispatched": ["start_9000001"], "remaining": ["start_9000002", "start_9000003"] }
```

| HTTP | Khi nào |
|------|---------|
| `200` | Batch đang mở → đóng, `stopReason = canceled` |
| `409` | Không có batch đang chạy |

Lệnh đã gửi ICS **không** bị huỷ — vẫn chờ ICS báo `3`/`23` để gỡ lock.

---

## `POST /runtime/pause-scan`

Dừng inference **và** huỷ batch (`stopReason` về `null`). Bắt buộc trước khi ghi cấu hình (nếu không → `409`).

---

## Gợi ý UI

- Nút **Bật camera** (`start-cameras`) → **Gửi robot** (`dispatch`), disable khi `batch.active`.
- Banner:
  - `batch_complete` → "Đã gửi hết đợt — đẩy hàng đợt mới rồi Gửi robot".
  - `canceled` → "Đã huỷ đợt".
  - `waitingFor` khác rỗng → "Zone {zoneId} chờ lệnh trước xong".
  - `stuckNodes` khác rỗng → cảnh báo mất hàng + nút **Huỷ đợt** (`cancel-batch`).
  - `newNodesOutsideBatch` khác rỗng → "Có hàng mới ngoài đợt — sẽ gửi ở đợt sau".
