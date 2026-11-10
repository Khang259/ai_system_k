# API `/api/v1` — Response & status_code (FE)

> Cập nhật: **2026-09-29**  
> Mục đích: **một file tra cứu** response thành công + HTTP status khi gọi API để FE tích hợp.  
> Nguồn sự thật: `presentation/routes/v1/*` + use case `application/fe_api/*`, `application/auth/*`, `application/cameras/*`.  
> Contract chi tiết từng nhóm: xem mục [Liên kết](#13-liên-kết).

---

## 0. Quy ước chung

| | Giá trị |
|---|---|
| Prefix | `/api/v1/{resource}/{verb}` (RPC-style) |
| Auth | `Authorization: Bearer <accessToken>` — trừ ghi chú riêng |
| Field JSON | **camelCase** |
| Thành công | Data **trần** — **không** bọc `{ success: true }` |
| Lỗi | HTTP status thật + `{ "message": "..." }` |
| Validation Pydantic | **422** — `message` có thể là chuỗi hoặc cấu trúc validation FastAPI |
| Binary | JPEG / ZIP / SDP — **không** JSON |

**Thuật ngữ ngắn**

| Từ | Nghĩa |
|---|---|
| **Bearer** | JWT access token trong header `Authorization` |
| **RPC-style** | Path dạng `/resource/verb`, không REST thuần `PATCH /resource/{id}` |
| **Inference gate** | Đang scan AI → nhiều API ghi config trả **409** (phải `pause-scan` trước) |

### Auth lỗi dùng chung (mọi API có Bearer)

| Status | `message` điển hình |
|---:|---|
| **401** | `Thiếu Bearer token` |
| **401** | `Token không hợp lệ hoặc đã hết hạn` |
| **403** | `Thiếu quyền: <permission>` |

### Interceptor FE (bắt buộc)

Access TTL ~**15 phút**. Khi **401**:

1. `POST /api/v1/auth/refresh_token` với `refreshToken`
2. Lưu cặp token mới (token cũ **hết hiệu lực ngay**)
3. Retry request gốc
4. Refresh cũng **401** → màn login

### Status tra nhanh (toàn hệ)

| Code | Ý nghĩa FE |
|---:|---|
| **200** | OK — JSON hoặc binary |
| **201** | WHEP connect OK — body SDP text |
| **204** | OK — không body (`logout`) |
| **304** | Poll không đổi (`If-None-Match`) |
| **400** | Request / nghiệp vụ sai |
| **401** | Chưa login / token hết hạn |
| **403** | Thiếu permission hoặc tài khoản tắt |
| **404** | Không tìm thấy resource |
| **409** | Xung đột: inference đang chạy / đủ 4 slot WebRTC / camera chưa streaming / trùng pair… |
| **422** | Body/query không đúng schema |
| **429** | Login bị khoá tạm (sai quá nhiều) |
| **500** | Lỗi server hiếm |
| **503** | Runtime / MediaMTX / health degraded |

### Inference gate (409 chung)

Nhiều API ghi camera / node / pair / ROI khi inference đang chạy:

```json
{ "message": "Tắt inference trước khi chỉnh cấu hình (pause-scan / stop)" }
```

→ FE: gọi `POST /api/v1/runtime/pause-scan` rồi retry.

---

## 1. Auth — `/api/v1/auth`

### `POST /api/v1/auth/login`

Auth: **không** Bearer.

**Request**

```json
{ "username": "admin", "password": "..." }
```

**200**

```json
{
  "accessToken": "eyJ...",
  "refreshToken": "...",
  "expiresIn": 900,
  "user": {
    "id": "...",
    "name": "...",
    "role": "admin",
    "permissions": ["camera.read", "camera.write"]
  }
}
```

| Status | `message` |
|---:|---|
| **401** | `Invalid username or password` |
| **403** | `Tài khoản đã bị vô hiệu hoá` |
| **429** | `Quá nhiều lần đăng nhập sai. Thử lại sau 15 phút.` |

---

### `POST /api/v1/auth/refresh_token`

Auth: **không** Bearer. Body: `{ "refreshToken": "..." }`  
**200**: cùng shape login.

| Status | `message` |
|---:|---|
| **401** | `Refresh token không hợp lệ` |
| **401** | `Phiên đã hết hạn, đăng nhập lại` |
| **401** | `Tài khoản không còn hiệu lực` |

---

### `GET /api/v1/auth/get_me`

Bearer. **200**: `{ id, name, role, permissions[] }`

| Status | `message` |
|---:|---|
| **401** | auth chung |
| **404** | `Không tìm thấy user` |

---

### `POST /api/v1/auth/logout`

Bearer. **204** — không body.

| Status | Khi nào |
|---:|---|
| **401** | Token thiếu / sai |

---

## 2. Cameras — `/api/v1/cameras`

### `GET /get_cameras` — `camera.read`

**200**

```json
{
  "items": [
    {
      "cameraId": 20,
      "name": "...",
      "rtspUrl": "rtsp://...",
      "zone": "AE5",
      "status": "streaming",
      "resolution": null,
      "mapPosition": null,
      "observedNodeIds": ["start_10000060"],
      "enabled": true,
      "error": null
    }
  ]
}
```

`status`: `disabled` | `offline` | `streaming`

| Status | Khi nào |
|---:|---|
| **401** / **403** | Auth |

---

### `GET /get_snapshot?cameraId=` — `camera.read`

**200** — binary `image/jpeg` (640×480)

| Status | `message` / ý nghĩa |
|---:|---|
| **404** | Camera không tồn tại |
| **409** | Camera chưa streaming |
| **503** | Runtime chưa sẵn / chưa có frame |

---

### `GET /get_rois?cameraId=` (optional) — `camera.read`

**200**

```json
{
  "items": [
    {
      "id": "20:start_10000060",
      "cameraId": 20,
      "nodeId": "start_10000060",
      "label": "...",
      "kind": "Start",
      "box": [10, 20, 100, 80],
      "refWidth": 640,
      "refHeight": 480
    }
  ]
}
```

---

### `POST /set_camera_status` — `camera.write`

**Request:** `{ "cameraId": 20, "enabled": true }`

**200:** `{ "cameraId", "enabled", "nodesUpdated", "pairsUpdated" }`

| Status | `message` |
|---:|---|
| **404** | `Camera {id} not found` |
| **409** | Inference gate |

---

### `PATCH /update_camera` — `camera.write`

**Request:** `{ "cameraId", "name?", "rtspUrl?", "zone?", "observedNodeIds?" }`

**200:** object camera + field cascade (`requiresRestart`, `nodesZoneUpdated`, `observedAssigned` / `Removed` / `Created`, `pairsDeleted`, …)

| Status | `message` |
|---:|---|
| **400** | Field rỗng / nodeId prefix sai |
| **404** | Camera không tồn tại |
| **409** | Node thuộc camera khác / inference gate |

---

### `POST /delete_camera` — `camera.write`

**200:** `{ "cameraId", "deleted": true, "nodesDeleted": [], "pairsDeleted": [] }`

| Status | `message` |
|---:|---|
| **404** | Camera không tồn tại |
| **409** | Inference gate |
| **500** | `Không xóa được camera …` |

---

### `POST /create_roi` — `camera.write`

**Request:** `{ "cameraId", "nodeId", "box": [x,y,w,h] }`  
**200:** một ROI item (như `get_rois`)

| Status | `message` |
|---:|---|
| **400** | Box / node không thuộc `observedNodeIds` |
| **404** | Camera / node không tồn tại |
| **409** | Inference gate |
| **500** | `Không ghi được ROI` |

---

### `PATCH /update_roi` — `camera.write`

**Request:** `{ "items": [ { "id"|"cameraId"+"nodeId", "box" }, ... ] }`  
**200:** `{ "items": [ ROI… ] }`

| Status | `message` |
|---:|---|
| **400** | `Cần ít nhất 1 ROI…` / `items[i]: …` |
| **404** | ROI / camera không tồn tại |
| **409** | Inference gate |

---

### `POST /delete_roi` — `camera.write`

**200:** `{ "id", "deleted": true, "pairsDeleted": [] }`

| Status | `message` |
|---:|---|
| **400** | Thiếu `id` hoặc `cameraId`+`nodeId` |
| **404** | `ROI không tồn tại` / camera |
| **409** | Inference gate |

---

### WebRTC (tóm tắt)

Chi tiết contract: [fe-api-webrtc.md](./fe-api-webrtc.md)

| Endpoint | Success | Lỗi chính |
|---|---|---|
| `GET /webrtc/ice` | **200** `{ iceServers }` | 401/403 |
| `GET /webrtc/status` | **200** `{ count, max }` | 401/403 |
| `POST /{id}/webrtc/preview/whep` | **201** SDP + `Location` | 400 / 404 / **409** max 4 / **503** |
| `POST /{id}/webrtc/detect/whep` | **201** SDP + `Location` | giống preview |
| `DELETE /{id}/webrtc/sessions/{sid}` | **200** `{ session_id, camera_id }` | **404** `Session not found` |
| `GET /{id}/preview/meta` | **200** `{ w, h, ts, rois, dets }` | 404 / 409 not streaming / 503 |

---

## 3. Nodes — `/api/v1/nodes`

### `GET /get_nodes?zoneId=` — `node.read`

**200**

```json
{
  "items": [
    {
      "id": "start_10000060",
      "nodeId": "start_10000060",
      "label": "...",
      "kind": "Start",
      "zoneId": "AE5",
      "cameraId": 20,
      "priority": 1,
      "enabled": true,
      "position": null,
      "isUnderMaintenance": false,
      "maintenanceReason": null,
      "lock": { "user": false, "system": false, "orderId": null }
    }
  ]
}
```

---

### `GET /get_runtime_state` — Bearer (mọi user login)

**200**

```json
{
  "runtimeReady": true,
  "items": [
    {
      "nodeId": "start_10000060",
      "detected": true,
      "isReady": false,
      "lock": { "user": false, "system": true, "orderId": "ORD-1" }
    }
  ]
}
```

Runtime chưa bind → vẫn **200** với `runtimeReady: false`, `items: []`.

---

### `PATCH /update_node` — `camera.write`

**200:** một node item.  
**400** / **404** / **409** (inference nếu áp dụng).

---

### `POST /delete_node` — `camera.write`

**200:** `{ "nodeId", "deleted": true, "roiDeleted", "pairsDeleted" }`  
**404** / **409** inference.

---

### `POST /set_maintenance` — `node.maintenance`

**200:** `{ "nodeId", "isUnderMaintenance", "maintenanceReason" }`

| Status | `message` |
|---:|---|
| **400** | `Cần maintenanceReason khi bật bảo trì` |
| **404** | `Node … not found` |

---

### `POST /set_lock` — `node.maintenance`

**200:** `{ "nodeId", "lock" }`

| Status | `message` |
|---:|---|
| **400** | `Dùng /unlock để tắt lock (user/system)` |
| **404** | Node không tồn tại |

---

### `POST /unlock` — `node.maintenance`

**Request:** `{ "nodeId", "user"?, "system"? }`  
**200:** `{ "nodeId", "lock" }`

| Status | `message` |
|---:|---|
| **400** | `Cần user=true và/hoặc system=true` |
| **404** | Node không tồn tại |

---

### `POST /unlock_by_order` — **không Bearer** (ICS / external)

**Request:** `{ "orderId": "...", "status": 3 | 23 }`

**200**

```json
{
  "message": "...",
  "orderId": "...",
  "reset_pairs": [["start_…", "end_…"]]
}
```

(`reset_pairs` có khi status **23** hoặc fallback clear lock.)

| Status | `message` |
|---:|---|
| **400** | `State manager not initialized` |
| **400** | `orderId … not found` |
| **400** | `Unknown status …` |
| **400** | `Reset failed` |

---

## 4. Pairs — `/api/v1/pairs`

### `GET /get_pairs?zoneId=` — `pair.read`

**200**

```json
{
  "items": [
    {
      "id": "start_…__end_…",
      "name": null,
      "zoneId": "AE5",
      "startNodeId": "start_…",
      "endNodeId": "end_…",
      "pairType": "normal",
      "enabled": true,
      "autoDispatch": true,
      "isBlocked": false,
      "blockedReason": null
    }
  ]
}
```

---

### `POST /create_pair` — `pair.write`

**200:** `{ id, startNodeId, endNodeId, zoneId, pairType, enabled, autoDispatch, runtimeReloaded }`

| Status | `message` |
|---:|---|
| **400** | `pairType phải là normal hoặc empty` / thiếu `endNodeId` / zone / node ROI |
| **409** | `Pair đã tồn tại` / inference gate |

---

### `PATCH /update_pair` — `pair.write`

**200:** giống fields create.  
**400** / **404** `Pair không tồn tại` / **409** trùng / inference.

---

### `POST /delete_pair` — `pair.write`

**200:** `{ id, startNodeId, endNodeId, runtimeReloaded }`  
**400** identity / **404** / **409** inference.

---

### `POST /set_pair_enabled` — `pair.write`

**200:** `{ id, startNodeId, endNodeId, enabled, runtimeReloaded }`  
**404** / **409** inference.

---

## 5. Zones — `/api/v1/zones`

### `GET /get_zones` — `camera.read`

**200**

```json
{
  "items": [
    {
      "id": "AE5",
      "name": "AE5",
      "isRunning": true,
      "isConfigEnabled": true,
      "cameraCount": 2,
      "nodeCount": 4,
      "lastChangedAt": null,
      "lastChangedBy": null
    }
  ]
}
```

---

### `POST /start_zone` / `POST /stop_zone` — `zone.control`

**Request:** `{ "zoneId": "AE5" }`  
**200:** `{ "message": "Zone AE5 enabled|disabled", "enabled": [...] }`

| Status | `message` |
|---:|---|
| **503** | `System not initialized` |
| **401** / **403** | Auth / thiếu `zone.control` |

---

## 6. System — `/api/v1/system`

### `GET /get_health` — Bearer

**200**

```json
{
  "status": "ok",
  "service": "AMR Camera Dispatch System",
  "mongo": true,
  "runtime_running": true,
  "webrtc": { "alive": true, "owned": true, "watchdog": {} }
}
```

**503** (degraded) — vẫn trả các field trên + `status: "degraded"` + `message`:

```json
{
  "status": "degraded",
  "message": "degraded: mongo, runtime không sẵn sàng",
  "mongo": false,
  "runtime_running": false,
  "webrtc": { "alive": false }
}
```

---

### `POST /start-cameras` — `system.control`

**200:** `{ "message": "Cameras started and scanning", "total", "enabled", "streaming", "cameras", "warnings", "scanning": true }` — bật camera **và** inference.

| Status | Khi nào |
|---:|---|
| **503** | System / model chưa sẵn / không camera nào streaming |
| **403** | Thiếu `system.control` |

---

### `POST /start_all` — `system.control` *(deprecated → `/start-cameras`)*

**200:** `{ "message": "Cameras started", "total", "enabled", "streaming", "cameras", "warnings", "scanning": false }` — chỉ bật camera, inference vẫn pause.

| Status | Khi nào |
|---:|---|
| **503** | System / model chưa sẵn / không camera nào streaming |
| **403** | Thiếu `system.control` |

---

### `POST /stop_all` — `system.control`

**200:** `{ "message": "All cameras disabled" }`  
**503:** `System not initialized`

---

## 7. Runtime — `/api/v1/runtime`

### `GET /get_status` — Bearer

**200:** `{ running, cameras: { total, enabled, alive }, inference: { paused }, strategy, started_at }`

---

### `POST /reload` — `system.control`

**200:** status object sau reload. **503** nếu runtime không reload được.

---

### `POST /start-scan` — `system.control` *(deprecated → `/system/start-cameras`)*

**200:** `{ "message": "Scanning started" }` — chỉ bật inference, chưa gửi ICS.

| Status | Khi nào |
|---:|---|
| **400** | System chưa sẵn / chưa start camera |

---

### `POST /dispatch` — `system.control` (alias deprecated: `/confirm-dispatch`)

**200:** `{ "message": "Dispatch confirmed", "batchSize", "batchNodes", "filledNodes" }`

| Status | Khi nào |
|---:|---|
| **400** | System chưa sẵn |
| **409** | Inference đang pause / batch trước chưa xong / chưa có start isReady / mọi col bị `lock.user` chặn |

---

### `GET /get_pending_pairs` — đã login

**200:** `{ runtimeReady, batch, readyStarts, nextPairs, waitingFor, filledNodes, stuckNodes, colStatus, newNodesOutsideBatch }` — xem [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md).

---

### `POST /cancel-batch` — `system.control`

**200:** `{ "message": "Batch canceled", "dispatched", "remaining" }` — đóng cổng, inference vẫn chạy.

| Status | Khi nào |
|---:|---|
| **409** | Không có batch đang chạy |

---

### `POST /pause-scan` — `system.control`

**200:** `{ "message": "Scanning paused" }`  
**400:** `System not initialized`

---

### `GET /events` — SSE

Auth: Bearer **hoặc** `?access_token=<jwt>`  
**200** `text/event-stream`:

- `event: node.runtime` + `data: <JSON>`
- heartbeat: `event: ping` + `data: {}`

**401** nếu thiếu / sai token.

---

## 8. Poll — `/api/v1/poll`

### `GET /get_snapshot?include=` — Bearer

Query `include`: `cameras,zones,notifications,map,nodes` (bỏ trống = tất cả).  
Header optional: `If-None-Match: "<etag>"`

**200**

```json
{
  "serverTime": "...",
  "pollIntervalSec": 2,
  "etag": "...",
  "cameras": { "items": [] },
  "zones": { "items": [] },
  "notifications": { "items": [], "total": 0 },
  "map": {},
  "nodes": { "runtimeReady": true, "items": [] }
}
```

Header response: `ETag`, `Cache-Control: no-store`

| Status | Khi nào |
|---:|---|
| **304** | Không đổi so với `If-None-Match` (body rỗng) |
| **401** | Auth |

---

## 9. Maps — `/api/v1/maps`

| Endpoint | Auth | Success | Lỗi chính |
|---|---|---|---|
| `POST /import_map` (multipart `file`) | `map.write` | **200** `{ versionId, isActive, pruned, byteSize, checksum }` | **400** file rỗng / zip sai |
| `GET /list_map_versions` | `map.read` | **200** `{ items[], activeVersionId }` | 401/403 |
| `POST /set_active_map` `{ versionId }` | `map.write` | **200** `{ versionId, isActive }` | **404** version |
| `GET /get_compress?versionId=` | `map.read` | **200** `{ versionId, compress }` | **404** / **500** |
| `GET /download_map_zip?versionId=` | `map.read` | **200** `application/zip` | **404** |

---

## 10. Logs — `/api/v1/logs` (`logs.read`)

Vỏ chung **200:**

```json
{ "items": [], "total": 0, "page": 1, "pageSize": 20 }
```

Query: `page`, `pageSize`, `from`, `to`.

| Endpoint | Item chính |
|---|---|
| `GET /get_audit_logs` | `id, userName, role, action, ipAddress, device, occurredAt` |
| `GET /get_user_action_logs` | `id, userName, role, action, endpoint, ipAddress, status, occurredAt, changes, payload` |
| `GET /get_system_action_logs` | `id, orderId, action, result, errorMessage, startNodeId, endNodeId, zoneId, durationMs, occurredAt, …` |

Lỗi: chủ yếu **401** / **403**.

---

## 11. Notifications — `/api/v1/notifications`

### `GET /get_notifications` — `logs.read`

Query: `page`, `pageSize`, `unreadOnly`  
**200:** paged `{ items: [{ id, type, title, message, createdAt, readAt, meta, snapshotImageUrl }], total, page, pageSize }`

### `POST /mark_read` `{ "id" }` — Bearer

**200:** `{ "id", "read": true }` — **404** `Notification not found`

### `POST /mark_all_read` — Bearer

**200:** `{ "updated": <n> }`

---

## 12. Snapshots — `/api/v1/snapshots`

### `GET /get_image?file=` — `logs.read`

**200** — binary JPEG/PNG

| Status | `message` |
|---:|---|
| **400** | `Tên file không hợp lệ` / `Chỉ hỗ trợ ảnh JPEG/PNG` / path không hợp lệ |
| **404** | `Snapshot không tồn tại hoặc đã hết hạn` |

---

## 13. Liên kết

| File | Nội dung |
|---|---|
| [fe-api-v1-ready.md](./fe-api-v1-ready.md) | Auth + snapshot + start/stop |
| [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md) | Camera / ROI / node / pair — luật sync |
| [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md) | Scan + dispatch theo batch |
| [fe-api-webrtc.md](./fe-api-webrtc.md) | Contract WHEP live |
| [fe-api-node-runtime.md](./fe-api-node-runtime.md) | Runtime snapshot + SSE |
| [fe-api-v1-batch-polling.md](./fe-api-v1-batch-polling.md) | Poll + etag |
| [fe-api-v1-batch-map.md](./fe-api-v1-batch-map.md) | Map zip |
| [fe-api-v1-batch-4.md](./fe-api-v1-batch-4.md) | Logs + notifications |
| [fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md) | Webhook ICS gỡ lock theo orderId |
| [fe-api-unlock-by-system-user.md](./fe-api-unlock-by-system-user.md) | Operator set_lock / unlock_by_user |

---

## 14. Checklist FE đọc lỗi

```ts
// Axios / fetch — luôn đọc status + message
const status = error.response?.status;
const message = error.response?.data?.message; // string (hoặc validation 422)

if (status === 401) { /* refresh → retry → login */ }
if (status === 403) { /* ẩn nút / toast thiếu quyền */ }
if (status === 409 && String(message).includes("inference")) {
  /* gợi ý pause-scan */
}
```

**Không** kỳ vọng `{ success: false, error: "..." }` trên `/api/v1`.
