# API `/api/v1` — Node `lock` (user + system) + snapshot Mongo

> Cập nhật: 2026-09-11  
> Một field Mongo/API: **`lock`**. Không còn `POST /state/flag/{node_id}`.

---

## 1. Field `lock` (duy nhất)

Trên node (Mongo + `get_nodes`):

```json
"lock": {
  "user": false,
  "system": false,
  "orderId": null
}
```

| Key | Ai set | Ý nghĩa |
|---|---|---|
| `user` | Operator qua API | Khóa điểm khỏi auto-dispatch (persist restart) |
| `system` | Hệ thống sau ICS **thành công** (cả start + end) | Busy chờ AMR (persist restart) |
| `orderId` | Khi `system=true` | Order ICS liên quan |

PairManager **chặn** node nếu `user` **hoặc** `system`.  
Có thể vừa `isUnderMaintenance` vừa `lock.*` (độc lập).

---

## 2. API

### `POST /api/v1/nodes/set_lock`

Quyền: `node.maintenance`. Body:

```json
{ "nodeId": "start_10000060", "user": true }
```

Chỉ **bật** `lock.user`. Tắt → dùng `/unlock_by_user`.

### `POST /api/v1/nodes/unlock_by_user`

```json
{ "nodeId": "start_10000060" }
```

Gỡ **cả** `lock.user` và `lock.system`.  
Mở khóa xong → điểm **chờ lại timer** ready rồi mới vào list ghép.
Chi tiết: [fe-api-unlock-by-system-user.md](./fe-api-unlock-by-system-user.md).

### Webhook ICS

`POST /api/v1/external_server/unlock_by_order_status` `{ "orderId", "status" }` — gỡ `lock.system` theo order (RAM + Mongo). Xem [fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md).

### Đã gỡ

`POST /state/flag/{node_id}` — không dùng (không toggle busy tay qua route cũ).

---

## 3. Snapshot Mongo

Khi `ENABLE_SNAPSHOTS=true` + ICS **Single** OK → ghi JPEG + insert collection `snapshots` (`image_path` = basename).  
Contract FE đầy đủ: [fe-api-dispatch-snapshots.md](./fe-api-dispatch-snapshots.md).

---

## 4. Poll

`pollIntervalSec` khuyến nghị **2** giây (giảm từ 3).

---

## 5. Không làm

- `send_command`  
- SSE / sync position / PGM  

---

## 6. Checklist FE

- [ ] Đọc/hiện `lock.user` và `lock.system` (không dùng `commandLock` cũ)  
- [ ] `set_lock` / `unlock` thay cho mọi thao tác khóa điểm  
- [ ] Không gọi `/state/flag/...`  
- [ ] Poll ~2s; health + chuông như [fe-api-v1-batch-health-notif.md](./fe-api-v1-batch-health-notif.md)  
