# API `/api/v1` — Polling (+ nodes runtime)

> Cập nhật: 2026-09-21  
> Giải pháp: **poll + snapshot lúc vào app / reconnect**.  
> Runtime node realtime: thêm SSE — xem [fe-api-node-runtime.md](./fe-api-node-runtime.md).

Auth: Bearer (mọi user đã login).

---

## 1. Vì sao poll + snapshot

| Tình huống | Cách xử lý |
|---|---|
| Client offline lúc “có thay đổi” | Lúc vào lại **GET snapshot** → vẫn đúng trạng thái hiện tại |
| Đang mở UI | Poll định kỳ theo `pollIntervalSec` **hoặc** SSE `node.runtime` |
| Tiết kiệm băng thông | Gửi `If-None-Match: <etag>` → **304** nếu không đổi |

---

## 2. Endpoint gộp

### `GET /api/v1/poll/get_snapshot`

Query optional: `include=cameras,zones,notifications,map,nodes` (bỏ trống = tất cả).

**200**

```json
{
  "serverTime": "2026-09-21T09:00:00+00:00",
  "pollIntervalSec": 2,
  "etag": "abc…",
  "cameras": {
    "items": [
      {
        "cameraId": 1,
        "status": "streaming",
        "enabled": true,
        "zone": "AE5",
        "error": null
      }
    ]
  },
  "zones": {
    "items": [
      {
        "id": "AE5",
        "isRunning": true,
        "isConfigEnabled": true,
        "cameraCount": 2,
        "nodeCount": 8
      }
    ]
  },
  "notifications": { "unreadCount": 3 },
  "map": { "activeVersionId": "…" },
  "nodes": {
    "runtimeReady": true,
    "items": [
      {
        "nodeId": "start_10000060",
        "detected": true,
        "isReady": true,
        "lock": { "user": false, "system": false, "orderId": null }
      }
    ]
  }
}
```

`nodes.runtimeReady: false` + `items: []` khi runtime chưa bind — **HTTP 200**, không 500.

Header response: `ETag: "<etag>"`, `Cache-Control: no-store`.

**304** — body rỗng khi `If-None-Match` khớp etag hiện tại.

---

## 3. Pattern FE

```text
onAppStart / onWindowFocus / onReconnect:
  GET /api/v1/poll/get_snapshot     // snapshot đầy đủ (gồm nodes)

Sau snapshot:
  mở SSE /api/v1/runtime/events?access_token=…   // delta node.runtime
  (fallback) setInterval(pollIntervalSec) + If-None-Match
```

Chi tiết màn hình (ROI editor, bảng logs, compress map) **không** nhét vào poll — gọi endpoint riêng khi vào màn đó.

| Nhu cầu | Endpoint riêng |
|---|---|
| Full camera + ROI | `get_cameras` / `get_rois` |
| Node config / pairs | `nodes/get_nodes` / `pairs/get_pairs` |
| Runtime node only | `GET /api/v1/nodes/get_runtime_state` |
| Vẽ map | `maps/get_compress` |
| Danh sách thông báo | `notifications/get_notifications` |

---

## 4. Chu kỳ gợi ý

| Ngữ cảnh | Interval |
|---|---|
| Có SSE runtime | Poll config (cameras/zones/…) ~3–5s; runtime qua SSE |
| Không SSE | Poll full theo `pollIntervalSec` (~2s) |
| Tab ẩn | Dừng poll/SSE hoặc nới interval |
| Sau thao tác ghi | Snapshot **ngay** |

---

## 5. Checklist FE

- [ ] Snapshot ngay khi login / F5 / focus lại tab  
- [ ] Đọc `nodes` từ poll hoặc `get_runtime_state`  
- [ ] SSE `node.runtime` sau snapshot (xem contract runtime)  
- [ ] Badge chuông từ `notifications.unreadCount`  
- [ ] `If-None-Match` khi poll  
