# Contract FE — System action logs (outbound ICS + webhook)

> Cập nhật: 2026-10-01  
> Bổ sung / thay thế phần logs + notification trong [fe-api-v1-batch-4.md](./fe-api-v1-batch-4.md)  
> Liên quan unlock: [fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md)

Auth: Bearer JWT + quyền **`logs.read`**.

**Thuật ngữ**

| Từ | Nghĩa |
|----|--------|
| **Outbound ICS** | BE chủ động `POST` sang `ICS_URL` (tạo lệnh AMR) |
| **Webhook vào BE** | External gọi `POST /external_server/unlock_by_order_status` |
| **`dispatch_logs`** | Collection Mongo; FE đọc qua `get_system_action_logs` |
| **`result`** | `"success"` \| `"failed"` — kết quả sự kiện |

---

## Breaking changes (FE phải đổi)

| Trước | Sau |
|-------|-----|
| ICS outbound **fail** → notification `type: "dispatch.failed"` | **Không còn** tạo notification này |
| ICS outbound **success** không vào system logs | Có — `action: "dispatch"`, `result: "success"` |
| ICS outbound **fail** chỉ thấy ở chuông | Xem trong `get_system_action_logs` (`result: "failed"`) |

> Bản ghi notification `dispatch.failed` cũ (nếu còn trong DB) vẫn list được; BE **không tạo mới**.

---

## Nguồn sự kiện trong `get_system_action_logs`

| `action` | Ai tạo | Khi nào |
|----------|--------|---------|
| `dispatch` | PairManager → outbound ICS | Mỗi lần gửi lệnh (success **và** fail) |
| `unlock_by_order_status` | External webhook | `POST /api/v1/external_server/unlock_by_order_status` |

Cả hai đều `externalSource: "ICS"` (mặc định).

---

## `GET /api/v1/logs/get_system_action_logs`

### Request

```http
GET /api/v1/logs/get_system_action_logs?page=1&pageSize=20&from=2026-10-01T00:00:00Z&to=2026-10-02T00:00:00Z
Authorization: Bearer <access_token>
```

| Query | Type | Mặc định | Mô tả |
|-------|------|----------|--------|
| `page` | `number` | `1` | Trang (≥ 1) |
| `pageSize` | `number` | `20` | 1–100 |
| `from` | `string` ISO-8601 | — | Lọc theo `occurredAt` (field Mongo `dispatched_at`) |
| `to` | `string` ISO-8601 | — | Cận trên |

### Response `200`

```json
{
  "items": [
    {
      "id": "S-10000060-10000061-2026-10-01 18:00:00.123456",
      "orderId": "S-10000060-10000061-2026-10-01 18:00:00.123456",
      "action": "dispatch",
      "result": "success",
      "errorMessage": null,
      "startNodeId": "start_10000060",
      "endNodeId": "end_10000061",
      "zoneId": null,
      "durationMs": null,
      "occurredAt": "2026-10-01T11:00:00+00:00",
      "externalSource": "ICS",
      "endpoint": "http://192.168.1.4:7000/ics/taskOrder/addTask",
      "requestPayload": {
        "modelProcessCode": "SingleGroupAE5",
        "fromSystem": "ICS",
        "orderId": "S-10000060-10000061-2026-10-01 18:00:00.123456",
        "taskOrderDetail": [{ "taskPath": "10000060,10000061" }]
      },
      "responsePayload": { "ok": true }
    },
    {
      "id": "S-10000062-10000063-...",
      "orderId": "S-10000062-10000063-...",
      "action": "dispatch",
      "result": "failed",
      "errorMessage": "ICS request failed",
      "startNodeId": "start_10000062",
      "endNodeId": "end_10000063",
      "zoneId": null,
      "durationMs": null,
      "occurredAt": "2026-10-01T11:01:00+00:00",
      "externalSource": "ICS",
      "endpoint": "http://192.168.1.4:7000/ics/taskOrder/addTask",
      "requestPayload": { "...": "..." },
      "responsePayload": {}
    },
    {
      "id": "ORD-1",
      "orderId": "ORD-1",
      "action": "unlock_by_order_status",
      "result": "success",
      "errorMessage": null,
      "startNodeId": null,
      "endNodeId": null,
      "zoneId": null,
      "durationMs": null,
      "occurredAt": "2026-10-01T11:05:00+00:00",
      "externalSource": "ICS",
      "endpoint": "/api/v1/external_server/unlock_by_order_status",
      "requestPayload": { "orderId": "ORD-1", "status": 3 },
      "responsePayload": { "message": "Flags reset for orderId ORD-1", "orderId": "ORD-1" }
    }
  ],
  "total": 3,
  "page": 1,
  "pageSize": 20
}
```

### Field item

| Field | Type | Mô tả |
|-------|------|--------|
| `id` | `string` | Ưu tiên Mongo id; fallback `orderId` |
| `orderId` | `string \| null` | ID lệnh ICS |
| `action` | `string` | `dispatch` \| `unlock_by_order_status` (và giá trị khác nếu BE thêm sau) |
| `result` | `string` | `success` \| `failed` |
| `errorMessage` | `string \| null` | Có khi fail (vd `"ICS request failed"`) |
| `startNodeId` | `string \| null` | Có với outbound `dispatch`; webhook unlock thường `null` |
| `endNodeId` | `string \| null` | Như trên |
| `zoneId` | `string \| null` | Có thể `null` (BE chưa luôn điền) |
| `durationMs` | `number \| null` | Thường `null` với outbound hiện tại |
| `occurredAt` | `string` ISO | Thời điểm ghi |
| `externalSource` | `string` | Mặc định `"ICS"` |
| `endpoint` | `string \| null` | URL ICS (outbound) hoặc path webhook |
| `requestPayload` | `object \| null` | Body đã gửi / nhận |
| `responsePayload` | `object \| null` | Outbound success: `{ "ok": true }`; fail: `{}` |

### Lỗi

| HTTP | Ý nghĩa |
|------|---------|
| `401` | Thiếu / sai Bearer |
| `403` | Thiếu `logs.read` |

---

## UI gợi ý

| Cần | Dùng |
|-----|------|
| Lịch sử lệnh gửi ICS (ok + fail) | Tab system logs, filter/badge theo `action === "dispatch"` và `result` |
| Lịch sử mở khóa từ AMR | `action === "unlock_by_order_status"` |
| Cảnh báo lệnh fail realtime | **Không** dựa chuông `dispatch.failed` nữa — poll system logs hoặc badge từ poll khác nếu FE tự làm |

### Ví dụ TypeScript

```ts
type SystemActionLog = {
  id: string;
  orderId: string | null;
  action: string;
  result: "success" | "failed" | string;
  errorMessage: string | null;
  startNodeId: string | null;
  endNodeId: string | null;
  zoneId: string | null;
  durationMs: number | null;
  occurredAt: string | null;
  externalSource: string;
  endpoint?: string | null;
  requestPayload?: Record<string, unknown> | null;
  responsePayload?: Record<string, unknown> | null;
};

async function getSystemActionLogs(
  accessToken: string,
  q: { page?: number; pageSize?: number; from?: string; to?: string } = {},
) {
  const params = new URLSearchParams();
  params.set("page", String(q.page ?? 1));
  params.set("pageSize", String(q.pageSize ?? 20));
  if (q.from) params.set("from", q.from);
  if (q.to) params.set("to", q.to);

  const res = await fetch(`/api/v1/logs/get_system_action_logs?${params}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
  return data as {
    items: SystemActionLog[];
    total: number;
    page: number;
    pageSize: number;
  };
}

function isDispatchFailed(row: SystemActionLog) {
  return row.action === "dispatch" && row.result === "failed";
}
```

---

## Ghi chú

- Outbound ghi **mọi** lần `send` (sau retry trong gateway vẫn fail → một bản ghi `failed`).
- Webhook `unlock_by_order_status` ghi `dispatch_logs` cả khi thành công lẫn thất bại (`422` validation thì không ghi).
- Notifications API vẫn hoạt động; chỉ **ngừng produce** `dispatch.failed` từ PairManager.
