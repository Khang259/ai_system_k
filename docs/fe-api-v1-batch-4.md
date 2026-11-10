# API `/api/v1` — Đợt 4 (logs + notifications + snapshot ảnh)

> Cập nhật: 2026-10-01  
> Phạm vi **chỉ** logs, notifications, lấy ảnh snapshot.  
> Đợt 1: [fe-api-v1-ready.md](./fe-api-v1-ready.md) · Camera/node/pair: [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md)  
> **System logs (outbound ICS):** xem contract mới [fe-api-system-action-logs.md](./fe-api-system-action-logs.md)

**Giả định:** FE đã có Bearer + refresh interceptor.

**Đã xác nhận backend (2026-09-10):** sau reload, `GET /api/v1/nodes/get_nodes` và `GET /api/v1/cameras/get_cameras` có trong app (Swagger tag `nodes-v1` / `cameras-v1`).

---

## 1. Phân trang chung

Mọi list đợt này:

```json
{ "items": [ ... ], "total": 48, "page": 1, "pageSize": 20 }
```

Query: `page` (mặc định 1), `pageSize` (1–100, mặc định 20).  
Lọc thời gian (ISO-8601): `from`, `to` (logs).

Quyền đọc logs / xem snapshot / list notifications: **`logs.read`**.

---

## 2. Logs

### `GET /api/v1/logs/get_audit_logs`

Đăng nhập / sự kiện auth.

```json
{
  "items": [
    {
      "id": "...",
      "userName": "admin",
      "role": "admin",
      "action": "login_success",
      "ipAddress": "10.0.0.1",
      "device": "Chrome · Windows",
      "occurredAt": "2026-09-10T03:00:00+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```

### `GET /api/v1/logs/get_user_action_logs`

Thao tác FE ghi qua `/api/v1` (ROI, maintenance, camera status…).

```json
{
  "id": "...",
  "userName": "op",
  "role": "operator",
  "action": "create_roi",
  "endpoint": "/api/v1/cameras/create_roi",
  "ipAddress": "127.0.0.1",
  "status": 200,
  "occurredAt": "...",
  "changes": null,
  "payload": { "cameraId": 1, "nodeId": "start_..." }
}
```

Token/password trong payload đã được redact `***` phía server.

### `GET /api/v1/logs/get_system_action_logs`

`dispatch_logs` — **outbound ICS** (success + fail, `action: "dispatch"`) và webhook `unlock_by_order_status`.

> Contract đầy đủ + breaking (bỏ notification `dispatch.failed`): [fe-api-system-action-logs.md](./fe-api-system-action-logs.md)

```json
{
  "id": "...",
  "orderId": "ORD-1",
  "action": "dispatch",
  "result": "success",
  "errorMessage": null,
  "startNodeId": "start_10000060",
  "endNodeId": "end_10000760",
  "zoneId": null,
  "durationMs": null,
  "occurredAt": "...",
  "externalSource": "ICS",
  "endpoint": "http://…/ics/taskOrder/addTask",
  "requestPayload": {},
  "responsePayload": { "ok": true }
}
```

---

## 3. Notifications

### `GET /api/v1/notifications/get_notifications`

Query: `page`, `pageSize`, `unreadOnly` (bool).

Trả thông báo của user hiện tại + broadcast (`user_id` null).

```json
{
  "items": [
    {
      "id": "...",
      "type": "info",
      "title": "...",
      "message": "...",
      "createdAt": "...",
      "readAt": null,
      "meta": {},
      "snapshotImageUrl": "/api/v1/snapshots/get_image?file=order1_....jpg"
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```

`snapshotImageUrl` có thể `null` (hết hạn / chưa gắn file). FE hiện “ảnh đã hết hạn” khi GET ảnh 404.

### `POST /api/v1/notifications/mark_read`

Cần Bearer (mọi role đã login).

```json
{ "id": "..." }
```

### `POST /api/v1/notifications/mark_all_read`

Không body → `{ "updated": N }`.

> **Breaking 2026-10-01:** BE **không còn** tạo notification `type: "dispatch.failed"` khi ICS outbound fail. Xem fail trong [get_system_action_logs](./fe-api-system-action-logs.md) (`action: "dispatch"`, `result: "failed"`).

---

## 4. Snapshot ảnh

### `GET /api/v1/snapshots/get_image?file={filename}`

| | |
|---|---|
| Quyền | `logs.read` |
| Response | Binary JPEG/PNG |
| An toàn | Chỉ **tên file** trong `SNAPSHOT_DIR` — không path `../` |

Ví dụ axios: `responseType: "blob"` + header Bearer.

**Vận hành:** đặt `ENABLE_SNAPSHOTS=true` trong `.env` thì pipeline mới ghi file khi dispatch thành công. Chưa bật → thư mục trống → 404.

---

## 5. Checklist FE

- [ ] Màn logs 3 tab → 3 endpoint trên, page-based  
- [ ] Chuông notifications + mark read / mark all  
- [ ] Ảnh snapshot: blob + xử lý 404 như hết hạn  
- [ ] UI theo `logs.read`  

---

## 6. Ghi chú — Node map

Map zip API đã ship — xem [fe-api-v1-batch-map.md](./fe-api-v1-batch-map.md).  
`position` / `mapPosition` trên nodes/cameras vẫn có thể `null` (FE không chờ BE sync từ compress).

---

## 7. Ngoài phạm vi / đã chốt không làm

| Mục | Trạng thái |
|---|---|
| SSE realtime | **Không làm** — dùng poll |
| `send_command` / lock session | **Không dùng** — xem [fe-api-v1-batch-snapshot-command.md](./fe-api-v1-batch-snapshot-command.md) |
| `commandLock` | Toggle `{ enabled }` — không phải lockedBy |
| Upload map + sync position / PGM | Map zip MVP đủ; **không** sync/PGM |
| Tự động insert notifications dispatch fail | **Đã gỡ** (2026-10-01) — fail nằm ở `get_system_action_logs` |
| ~~Ghi Mongo `snapshots` khi lưu file~~ | Đã làm `SnapshotIndexer` (cần `ENABLE_SNAPSHOTS=true`) |
