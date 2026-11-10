# API `/api/v1` — Health banner + notification khi dispatch fail

> Cập nhật: 2026-09-11  
> Phạm vi: **`get_health`** (prefix `/api/v1`) + **tự tạo notification** khi ICS gửi lệnh thất bại.  
> Auth / poll / map / logs: xem các file liên kết ở cuối.

**Giả định:** FE đã có Bearer + refresh interceptor (`401` → `refresh_token` → retry).

---

## 1. Health — banner hệ thống

### `GET /api/v1/system/get_health`

| | |
|---|---|
| Auth | Bearer — **mọi role đã login** |
| Quyền đặc biệt | **Không** cần `system.control` |
| Thay thế | FE **không** gọi `GET /health` (route ops, không Bearer) |

**200** — ổn:

```json
{
  "status": "ok",
  "service": "AMR Camera System",
  "mongo": true,
  "runtime_running": true,
  "webrtc": {
    "alive": true,
    "owned": true,
    "watchdog": true
  }
}
```

**503** — degraded (vẫn có đủ field trên + `message`):

```json
{
  "status": "degraded",
  "service": "AMR Camera System",
  "mongo": true,
  "runtime_running": false,
  "webrtc": { "alive": false, "owned": false, "watchdog": false },
  "message": "degraded: runtime không sẵn sàng"
}
```

### Cách FE dùng

| Field | Ý nghĩa gợi ý UI |
|---|---|
| `status` | `"ok"` → xanh; `"degraded"` → cảnh báo |
| `mongo` | DB sống / chết |
| `runtime_running` | Pipeline camera/dispatch có chạy không |
| `webrtc` | MediaMTX — **optional**; app vẫn chạy khi `alive=false` |
| `message` | Chỉ có khi 503 — hiện tooltip / dòng phụ |

**Gợi ý tần suất:** lúc vào app + mỗi 30–60s (hoặc cùng lúc poll). Không cần ETag.

> **Lưu ý:** HTTP 503 vẫn là “có body JSON hợp lệ”. Đừng chỉ đọc `message` rồi bỏ `mongo` / `runtime_running`.

---

## 2. Notification tự sinh khi dispatch fail

Khi backend gửi lệnh ICS mà gateway trả fail, hệ thống **tự insert** một notification broadcast.

| Field | Giá trị |
|---|---|
| `type` | `"dispatch.failed"` |
| `title` | `"Lệnh thất bại"` |
| `message` | Ví dụ: `ICS thất bại: start_… → end_…` |
| `user_id` | `null` → **mọi user** thấy (broadcast) |
| `meta.startNodeId` | Node start |
| `meta.endNodeId` | Node end |
| `meta.orderId` | Order ICS (có thể `null`) |
| `snapshotImageUrl` | Thường `null` (fail trước khi lưu ảnh) |

### FE đọc như thế nào

1. **Badge chuông** — từ poll:  
   `GET /api/v1/poll/get_snapshot` → `notifications.unreadCount`
2. **Danh sách** —  
   `GET /api/v1/notifications/get_notifications?page=1&pageSize=20`  
   (optional `unreadOnly=true`)
3. **Đánh dấu đã đọc** —  
   `POST /api/v1/notifications/mark_read` body `{ "id": "..." }`  
   hoặc `POST /api/v1/notifications/mark_all_read`

Quyền list notifications: **`logs.read`**. Mark read chỉ cần Bearer.

### Ví dụ item

```json
{
  "id": "...",
  "type": "dispatch.failed",
  "title": "Lệnh thất bại",
  "message": "ICS thất bại: start_10000060 → end_10000061",
  "createdAt": "2026-09-11T04:00:00+00:00",
  "readAt": null,
  "meta": {
    "startNodeId": "start_10000060",
    "endNodeId": "end_10000061",
    "orderId": "ORD-…"
  },
  "snapshotImageUrl": null
}
```

**UI gợi ý:** nhánh `type === "dispatch.failed"` → hiện start/end (và orderId nếu có) từ `meta`; không phụ thuộc ảnh.

---

## 3. Không dùng WebSocket cho health / chuông

| Cũ / sai | Đúng (phase hiện tại) |
|---|---|
| `WebSocket /ws` | **Không** — sẽ 403 |
| `GET /health` từ FE | Dùng `GET /api/v1/system/get_health` |
| SSE realtime | Chưa ship — dùng **poll** |

Chi tiết poll: [fe-api-v1-batch-polling.md](./fe-api-v1-batch-polling.md).

---

## 4. Checklist FE

- [ ] Đổi health URL → `/api/v1/system/get_health` + Bearer  
- [ ] Xử lý cả **200** và **503** với cùng shape field  
- [ ] Badge chuông từ `poll` → `notifications.unreadCount`  
- [ ] List + mark read; nhận diện `type: "dispatch.failed"`  
- [ ] Bỏ gọi WebSocket `/ws` (nếu còn)  
- [ ] Sau login lại / F5: snapshot poll ngay một lần  

---

## 5. Tài liệu liên quan

| File | Nội dung |
|---|---|
| [fe-api-v1-ready.md](./fe-api-v1-ready.md) | Auth, snapshot cam, zone/system start-stop, **get_health** |
| [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md) | Cameras / ROI / nodes / pairs |
| [fe-api-v1-batch-4.md](./fe-api-v1-batch-4.md) | Logs + notifications CRUD + snapshot file |
| [fe-api-v1-batch-map.md](./fe-api-v1-batch-map.md) | Map ZIP (import / compress / download) |
| [fe-api-v1-batch-polling.md](./fe-api-v1-batch-polling.md) | Poll snapshot + ETag |
| [fe-api-v1-batch-snapshot-command.md](./fe-api-v1-batch-snapshot-command.md) | Snapshot Mongo + không send_command + commandLock toggle |

---

## 6. Ngoài phạm vi (file này)

- SSE / WebSocket push  
- Notification cho mọi loại lỗi khác (chỉ ICS send fail MVP)  
- Gắn ảnh snapshot vào `dispatch.failed`  
