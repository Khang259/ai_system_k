# Contract FE — Active tasks (panel lệnh đang chạy)

> Cập nhật: 2026-10-05  
> Liên quan: [fe-api-start-priority.md](./fe-api-start-priority.md), [fe-api-system-action-logs.md](./fe-api-system-action-logs.md), [fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md)  
> Thay thế webhook cũ `POST /api/v1/nodes/unlock_by_system` (endpoint đã **xóa**)

Auth FE: Bearer. SSE: Bearer hoặc `?access_token=` (EventSource không gửi header).

---

## Mục tiêu

Operator xem các lệnh single đã gửi ICS thành công, sắp theo `priorityStart`, cập nhật realtime qua SSE. Sau restart / mở app: hydrate một lần bằng GET.

**Thuật ngữ**

| Từ | Nghĩa |
|----|--------|
| **active task** | Lệnh đang hiển thị trên panel (`issued` / `inprogress`) |
| **orderId** | `S-{startNum}-{endNum}-{datetime}` — khóa upsert / xóa trên FE |
| **priorityStart** | Priority Mongo của **start** (cùng nguồn sort dispatch; số nhỏ hiện trước) |
| **issued** | ICS đã nhận lệnh (status ICS `9`, hoặc vừa `gateway.send` OK) |
| **inprogress** | ICS báo đang chạy (status ICS `6`) |
| **Placed (23)** | ICS báo xong → BE gỡ lock + SSE xóa khỏi panel (FE **không** gọi API này) |

---

## Luật domain (chốt)

| # | Luật |
|---|------|
| 1 | Chỉ lệnh **single** dạng `orderId` bắt đầu `S-` (parse được start/end) |
| 2 | Panel chỉ hiển thị `issued` (9) và `inprogress` (6) |
| 3 | Gửi ICS OK → coi như **issued** ngay (không chờ webhook 9) |
| 4 | ICS status **3** (Canceled) hoặc **23** (Placed) → gỡ node lock + xóa order khỏi panel |
| 5 | Status khác (8 completed, …) → BE bỏ qua; FE không nhận event riêng |
| 6 | Sort: `priorityStart` ASC; thiếu priority → cuối; tie → `orderId` |
| 7 | Đổi priority DB chỉ đúng sau **restart runtime** (giống dispatch) |
| 8 | External webhook **không** Bearer — FE không gọi |

---

## Breaking changes

| Trước | Sau |
|-------|-----|
| `POST /api/v1/nodes/unlock_by_system` | **Xóa**. External đổi sang `POST /api/v1/external_server/unlock_by_order_status` |
| Webhook `status` 3 = “hoàn thành toàn bộ”, `23` = chỉ empty (BE cũ) | Cả **3** (Canceled) và **23** (Placed) đều gỡ lock + xóa panel (cùng hành vi) |
| Không có panel lệnh realtime | SSE `dispatch.task` / `dispatch.task.removed` + GET hydrate |

---

## Flow FE khuyến nghị

```
1) Mở EventSource  GET /api/v1/dispatch/events?access_token=...
2) GET /api/v1/dispatch/get_active_tasks   ← hydrate panel
3) SSE: event "dispatch.task"         → upsert theo orderId
       event "dispatch.task.removed" → xóa theo orderId
       event "ping"                  → bỏ qua (giữ kết nối)
```

**Thứ tự quan trọng:** mở SSE **trước** GET. Nếu GET trước rồi mới SSE, lệnh mới gửi ICS trong khoảng trống có thể lọt mất.

**Store FE:** map `orderId → item`. Sau mỗi upsert/removed, sort lại theo `priorityStart` ASC (BE đã sort trong GET; SSE từng item nên FE tự sort khi merge).

---

## A. `GET /api/v1/dispatch/get_active_tasks`

Hydrate sau restart / vào app. BE gọi ICS `getOrderList` (trang 1), lọc `OrderStatus ∈ {9,6}` + `OrderId` dạng `S-…`, đồng bộ panel RAM BE.

### Request

```http
GET /api/v1/dispatch/get_active_tasks
Authorization: Bearer <access_token>
```

Không query / body.

### Response `200`

```json
{
  "items": [
    {
      "orderId": "S-10000071-10000770-2026-10-03 09:52:00.000001",
      "startNodeId": "start_10000071",
      "endNodeId": "end_10000770",
      "priorityStart": 1,
      "status": "inprogress"
    },
    {
      "orderId": "S-10000061-10000761-2026-10-03 09:51:33.123456",
      "startNodeId": "start_10000061",
      "endNodeId": "end_10000761",
      "priorityStart": 2,
      "status": "issued"
    }
  ]
}
```

| Field | Type | Mô tả |
|-------|------|--------|
| `items` | `array` | Có thể `[]` |
| `items[].orderId` | `string` | Khóa duy nhất |
| `items[].startNodeId` | `string` | `start_<digits>` |
| `items[].endNodeId` | `string` | `end_<digits>` |
| `items[].priorityStart` | `number \| null` | Priority start; `null` nếu chưa có meta |
| `items[].status` | `"issued" \| "inprogress"` | Chỉ hai giá trị này |

### Lỗi

| HTTP | Khi nào | `message` (ví dụ) |
|------|---------|-------------------|
| `401` | Thiếu / sai token | `Thiếu Bearer token` |
| `502` | ICS getOrderList timeout / HTTP lỗi / `code != 1000` | `Không lấy được danh sách lệnh từ ICS: …` |

Không trả list rỗng khi ICS lỗi — luôn `502`.

---

## B. `GET /api/v1/dispatch/events` (SSE)

### Request

```http
GET /api/v1/dispatch/events
Authorization: Bearer <access_token>
```

hoặc

```http
GET /api/v1/dispatch/events?access_token=<access_token>
```

`Content-Type` response: `text/event-stream`.

### Event: `dispatch.task`

Upsert một lệnh (tạo mới hoặc đổi status).

```
event: dispatch.task
data: {"orderId":"S-10000061-10000761-2026-10-03 09:51:33.123456","startNodeId":"start_10000061","endNodeId":"end_10000761","priorityStart":2,"status":"issued"}
```

| Khi nào BE gửi | `status` |
|----------------|----------|
| ICS `send` OK | `"issued"` |
| Webhook ICS `status: 6` | `"inprogress"` |
| Webhook 6 mà panel chưa có order (sau restart) | `"inprogress"` (tự thêm) |

### Event: `dispatch.task.removed`

Xóa khỏi panel (ICS `status: 23`).

```
event: dispatch.task.removed
data: {"orderId":"S-10000061-10000761-2026-10-03 09:51:33.123456"}
```

### Event: `ping`

```
event: ping
data: {}
```

Heartbeat ~15s khi không có event — bỏ qua.

### Lỗi kết nối

| HTTP | Khi nào |
|------|---------|
| `401` | Thiếu / sai token |

Reconnect: mở lại SSE rồi gọi lại `get_active_tasks` (cùng thứ tự như flow trên).

---

## C. Mapping status (FE chỉ cần biết)

| ICS `status` / `OrderStatus` | FE `status` | Panel |
|------------------------------|-------------|--------|
| (gửi ICS OK, chưa webhook) | `issued` | Thêm / giữ |
| `9` Assigned | `issued` | Hydrate GET |
| `6` Running | `inprogress` | Upsert |
| `23` Placed | — | **Xóa** (`dispatch.task.removed`) |
| `3` Canceled | — | **Xóa** (`dispatch.task.removed`) — cùng hành vi với 23 |
| `8` Completed, khác | — | Không event; GET cũng lọc bỏ |

---

## D. Webhook External (không phải FE)

Chi tiết body phẳng + lỗi + log: **[fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md)**.

Tóm tắt: `POST /api/v1/external_server/unlock_by_order_status`, body root `orderId` + `status` (**int**), field thừa được bỏ qua. FE chỉ thấy hệ quả qua SSE.

---

## E. Checklist FE

- [ ] Store keyed by `orderId`
- [ ] SSE trước → GET hydrate sau
- [ ] `dispatch.task` → upsert; `dispatch.task.removed` → delete
- [ ] Sort UI theo `priorityStart` ASC
- [ ] Hiển thị label: `issued` / `inprogress` (không hardcode số ICS)
- [ ] `502` trên GET → toast lỗi ICS, **không** xóa panel cũ nếu đang reconnect (tùy UX; BE không trả `items` khi lỗi)
- [ ] Không còn gọi `unlock_by_system`
- [ ] Operator unlock tay vẫn dùng `POST /api/v1/nodes/unlock_by_user` (không đổi)

---

## F. Pseudo FE (gợi ý)

```ts
type ActiveTask = {
  orderId: string
  startNodeId: string
  endNodeId: string
  priorityStart: number | null
  status: "issued" | "inprogress"
}

// Map orderId → ActiveTask; sau mỗi thay đổi sort theo priorityStart rồi orderId
```
