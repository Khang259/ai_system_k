# Contract FE / External — Unlock by order status (webhook ICS)

> Cập nhật: 2026-10-05  
> Liên quan: [fe-api-active-tasks.md](./fe-api-active-tasks.md), [fe-api-system-action-logs.md](./fe-api-system-action-logs.md), [fe-api-unlock-by-system-user.md](./fe-api-unlock-by-system-user.md)  
> Thay thế: `POST /api/v1/nodes/unlock_by_system` (đã **xóa**)

**Ai gọi:** External / ICS → BE. **FE không gọi** endpoint này.  
FE chỉ nhận kết quả qua SSE `dispatch.task` / `dispatch.task.removed` (xem active-tasks).

Auth: **Không** Bearer.

---

## Mục tiêu

ICS báo trạng thái lệnh → BE:

| ICS `status` (number) | Hành vi BE | FE (SSE) |
|-----------------------|------------|----------|
| `6` | Panel → `inprogress` | `dispatch.task` |
| `9` | Panel → `issued` (ít gặp nếu đã issued lúc gửi ICS) | `dispatch.task` |
| `3` Canceled | Gỡ system-lock start/end + xóa panel | `dispatch.task.removed` |
| `23` Placed | Giống `3` | `dispatch.task.removed` |
| Khác (`2`, `8`, …) | Bỏ qua nghiệp vụ, vẫn `200` nếu body hợp lệ | Không event |

**Thuật ngữ:** body **phẳng** = `orderId` + `status` nằm ở root JSON (không bọc `{"payload":{...}}`).

---

## `POST /api/v1/external_server/unlock_by_order_status`

### Request

```http
POST /api/v1/external_server/unlock_by_order_status
Content-Type: application/json
```

**Không** header `Authorization`.

### Body — phẳng

```json
{
  "orderId": "S-10000060-10000061-2026-10-05 15:35:02.537472",
  "status": 23,
  "shelfCurrPosition": "10001546",
  "subTaskStatus": "3",
  "deviceCode": "EL21490AAK00007",
  "modelProcessCode": "SEGroupAF",
  "qrContent": "10001546",
  "processRate": "1/1"
}
```

| Field | Type | Bắt buộc | Mô tả |
|-------|------|----------|--------|
| `orderId` | `string` | Có | ID lệnh BE đã gửi ICS (vd. `S-…` single) |
| `status` | `number` (int) | Có | Mã task status ICS: `3`, `6`, `9`, `23`, … |
| *khác* | any | Không | BE **bỏ qua** (`extra = allow`) |

Ghi chú: Pydantic cũng chấp nhận `"23"` (string số) và coerce → `int`. Ưu tiên gửi **number** như mock.

**Không dùng** body kiểu cũ:

```json
{ "payload": { "orderId": "...", "status": 23 } }
```

→ `422` thiếu field root / sai shape.

### Response `200` (ví dụ)

```json
{
  "message": "orderId S-… → inprogress",
  "orderId": "S-10000060-10000061-2026-10-05 15:35:02.537472",
  "status": "inprogress"
}
```

Hoặc sau clear lock (`3` / `23`):

```json
{
  "message": "Flags reset for orderId S-…",
  "orderId": "S-…"
}
```

### Lỗi

| HTTP | Khi nào | Ghi `dispatch_logs`? |
|------|---------|----------------------|
| `422` | Thiếu `orderId` / `status`, hoặc `status` không phải số | **Không** (lỗi trước audit) |
| `400` | Use case fail (vd. `3`/`23` nhưng không tìm thấy lock / order) | **Có** (`action: unlock_by_order_status`, failed) |
| `200` | Xử lý OK hoặc status bỏ qua | **Có** (success) |

---

## Hành vi panel / lock (FE cần biết)

1. Gửi ICS OK → BE tự SSE `dispatch.task` với `status: "issued"`.
2. Webhook `6` → SSE `dispatch.task` với `status: "inprogress"`.
3. Webhook `3` hoặc `23` → gỡ `lock.system` + SSE `dispatch.task.removed`.
4. Operator unlock tay: `POST /api/v1/nodes/unlock_by_user` (JWT).

Chi tiết SSE + GET hydrate: [fe-api-active-tasks.md](./fe-api-active-tasks.md).

---

## Log

| Nguồn | API xem |
|-------|---------|
| Webhook vào BE | `GET /api/v1/logs/get_system_action_logs` — filter `action === "unlock_by_order_status"` |

---

## Checklist tích hợp External

- [ ] URL: `/api/v1/external_server/unlock_by_order_status`
- [ ] Body **phẳng**: `orderId` + `status` (**int**) ở root
- [ ] Không gửi Bearer
- [ ] `status` clear panel: `3` và `23`
- [ ] Field thừa được gửi kèm — OK

## Checklist FE (gián tiếp)

- [ ] Không gọi webhook này từ FE
- [ ] Lắng nghe SSE removed khi lệnh hủy / xong
- [ ] Log màn system-action: action `unlock_by_order_status`
