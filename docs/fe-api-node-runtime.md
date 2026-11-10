# Contract FE — Node runtime (snapshot + SSE)

> Cập nhật: 2026-09-21  
> Phạm vi: trạng thái vận hành node trên **RAM** (`detected` / `isReady` / `lock`).  
> Không đẩy detection lên Mongo; lock vẫn mirror Mongo + hydrate lúc start.

Auth: Bearer JWT — **mọi user đã login** (không cần `node.read`).  
SSE (EventSource): dùng `?access_token=<jwt>` vì trình duyệt không gửi header Authorization.

---

## Thuật ngữ

| Từ | Nghĩa |
|---|---|
| **Snapshot** | GET lấy toàn bộ trạng thái tại 1 thời điểm |
| **SSE** | Server-Sent Events — server đẩy delta một chiều qua HTTP |
| **detected** | Node đang “thấy” vật thể (`state` trong PairManager / NodeState) |
| **isReady** | Node nằm trong `ready_start_list` / `ready_end_list` (đúng PairManager) |
| **lock** | Khoá user / system (+ `orderId` khi system) |
| **runtimeReady** | Runtime đã bind NodeState vào process; `false` → chưa có RAM state |

---

## 1. Pattern FE (bắt buộc)

```text
onAppStart / onReconnect / onSSEError:
  1) GET snapshot (poll include=nodes  HOẶC  get_runtime_state)
  2) merge vào store (filter zone/camera trên FE)
  3) mở EventSource /api/v1/runtime/events?access_token=…

onSSE message event=node.runtime:
  upsert 1 item theo nodeId

onSSE error / close:
  đóng ES → snapshot lại → mở ES lại
```

**Không** tin SSE là đủ khi mới mở trang — luôn snapshot trước.

---

## 2. Snapshot riêng

### `GET /api/v1/nodes/get_runtime_state`

| | |
|---|---|
| Auth | `Authorization: Bearer <accessToken>` |
| Quyền | đã login |
| Scope | **all** nodes trong RAM — FE tự filter |

**200 — runtime sẵn**

```json
{
  "runtimeReady": true,
  "items": [
    {
      "nodeId": "start_10000060",
      "detected": true,
      "isReady": true,
      "lock": {
        "user": false,
        "system": true,
        "orderId": "ORD-1"
      }
    }
  ]
}
```

**200 — runtime chưa bind** (không 500)

```json
{
  "runtimeReady": false,
  "items": []
}
```

| Field | Ý nghĩa |
|---|---|
| `detected` | = `state` RAM |
| `isReady` | trong ready list PairManager |
| `lock.user` / `lock.system` | boolean |
| `lock.orderId` | string \| null (chỉ khi system lock) |

---

## 3. Snapshot qua poll

### `GET /api/v1/poll/get_snapshot?include=nodes`

Hoặc bỏ `include` (= tất cả, gồm `nodes`).

**Khối thêm:**

```json
{
  "nodes": {
    "runtimeReady": true,
    "items": [ /* cùng shape get_runtime_state */ ]
  }
}
```

`include` hợp lệ: `cameras,zones,notifications,map,nodes`.

Chi tiết poll: [fe-api-v1-batch-polling.md](./fe-api-v1-batch-polling.md).

---

## 4. SSE delta

### `GET /api/v1/runtime/events`

| | |
|---|---|
| Content-Type | `text/event-stream` |
| Auth | Bearer **hoặc** `?access_token=<jwt>` |
| Quyền | đã login |

**Event `node.runtime`** (một node đổi — debounce ~150ms)

```
event: node.runtime
data: {"nodeId":"start_10000060","detected":true,"isReady":true,"lock":{"user":false,"system":false,"orderId":null}}
```

**Event `ping`** (heartbeat ~15s khi không có delta)

```
event: ping
data: {}
```

Server **không** gửi full snapshot trên SSE — FE tự GET trước.

Debounce: nhiều đổi cùng node trong cửa sổ ngắn → một event cuối.

---

## 5. Checklist FE

- [ ] Vào app / reconnect → snapshot trước, rồi mới SSE  
- [ ] Store `Map<nodeId, RuntimeItem>`; filter zone trên FE  
- [ ] `runtimeReady === false` → UI “đang khởi động”, không toast lỗi 500  
- [ ] EventSource: `new EventSource(\`/api/v1/runtime/events?access_token=${token}\`)`  
- [ ] `addEventListener("node.runtime", …)` + `addEventListener("ping", …)`  
- [ ] Unlock UI: dùng `lock` từ store + API `POST /api/v1/nodes/unlock_by_user` (đã có)  
- [ ] Fallback: nếu SSE fail → poll `include=nodes` theo `pollIntervalSec`

---

## 6. Endpoint liên quan

| Mục đích | Path |
|---|---|
| Snapshot runtime | `GET /api/v1/nodes/get_runtime_state` |
| Poll (có nodes) | `GET /api/v1/poll/get_snapshot` |
| SSE | `GET /api/v1/runtime/events` |
| Unlock | `POST /api/v1/nodes/unlock_by_user` |
| Start / dispatch / pause | [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md) |
