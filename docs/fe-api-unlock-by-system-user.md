# Contract FE — Unlock node by user

> Cập nhật: 2026-11-10 (gỡ phần `unlock_by_system` — endpoint đã xoá)  
> Lock do ICS (`lock.system`) gỡ tự động qua webhook: [fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md).

**Thuật ngữ:** `lock.user` = khóa tay operator; `lock.system` = khóa theo lệnh ICS (`orderId`);
node **block** (không vào ready) khi một trong hai = true.

| API | Ai gọi | Auth | Log |
|-----|--------|------|-----|
| `POST /api/v1/external_server/unlock_by_order_status` | ICS | **Không** JWT | `get_system_action_logs` |
| `POST /api/v1/nodes/set_lock` | Operator FE | Bearer + `node.maintenance` | `get_user_action_logs` |
| `POST /api/v1/nodes/unlock_by_user` | Operator FE | Bearer + `node.maintenance` | `get_user_action_logs` |

---

## `POST /api/v1/nodes/set_lock`

Chỉ **bật** `lock.user`. Body: `{ "nodeId": "start_10000060", "user": true }`.  
Gửi `user: false` → `400` (dùng `unlock_by_user`).

## `POST /api/v1/nodes/unlock_by_user`

Operator gỡ **cả** `lock.user` + `lock.system` trên **một** `nodeId`.
Gỡ xong, node phải chờ lại đủ timer ready mới được ghép cặp.

```json
{ "nodeId": "start_10000060" }
```

### Response `200`

```json
{
  "nodeId": "start_10000060",
  "lock": { "user": false, "system": false, "orderId": null }
}
```

### Lỗi

| HTTP | Ý nghĩa |
|------|---------|
| `401` | Thiếu / sai Bearer |
| `403` | Thiếu `node.maintenance` |
| `404` | `{ "message": "Node … not found" }` |

Gỡ `lock.system` bằng tay **không** xoá lệnh bên ICS và không xoá khỏi panel active task —
chỉ dùng khi chắc chắn robot không còn chạy lệnh đó.

### Ví dụ TypeScript

```ts
async function unlockByUser(accessToken: string, nodeId: string) {
  const res = await fetch("/api/v1/nodes/unlock_by_user", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ nodeId }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
  return data as {
    nodeId: string;
    lock: { user: boolean; system: boolean; orderId: string | null };
  };
}
```
