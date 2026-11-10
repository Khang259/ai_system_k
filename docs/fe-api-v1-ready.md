# API `/api/v1` — Auth + alias (đợt 1)

> Cập nhật: 2026-09-10  
> Phạm vi: **Auth** + **snapshot / start-stop zone & system**.  
> Đọc/ghi camera, ROI, node, pair: xem [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md).  
> Bật camera + dispatch: [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md).

---

## 1. Quy ước chung

| | Giá trị |
|---|---|
| Prefix | `/api/v1/{resource}/{verb}` (RPC-style) |
| Auth | Header `Authorization: Bearer <accessToken>` — **bắt buộc** mọi endpoint dưới đây trừ `login` và `refresh_token` |
| Field JSON | **camelCase** (`cameraId`, `zoneId`, `accessToken`…) |
| Thành công | Data trần — **không** bọc `{ success: true }` |
| Lỗi | HTTP status thật + `{ "message": "..." }` |
| Zone id | Upper-case phía server (`ae5` → `AE5`). Gửi `AE5` hoặc `ae5` đều được |

### Interceptor bắt buộc

Access token TTL **15 phút**. Khi nhận `401`:

1. `POST /api/v1/auth/refresh_token` với `refreshToken` đang giữ  
2. Lưu cặp token mới (token cũ **mất hiệu lực ngay** — rotation)  
3. Retry request gốc  
4. Nếu refresh cũng `401` → đưa về màn login

### Quyền (không hardcode role)

Ẩn/hiện nút theo mảng `permissions` từ `login` / `get_me`:

| Quyền | Endpoint trong file này |
|---|---|
| `camera.read` | `get_snapshot` |
| `zone.control` | `start_zone`, `stop_zone` |
| `system.control` | `start_all`, `stop_all` — **chỉ admin** hiện có |

| Role | permissions (tham chiếu) |
|---|---|
| `admin` | tất cả 8 quyền |
| `operator` | `camera.read`, `camera.write`, `node.read`, `node.maintenance`, `zone.control`, `logs.read` |
| `viewer` | `camera.read`, `node.read`, `logs.read` |

Operator **không** có `system.control` → ẩn nút Start/Stop all hệ thống.

---

## 2. Auth — 4 endpoint

### `POST /api/v1/auth/login`

Không cần Bearer.

**Request**

```json
{ "username": "admin", "password": "..." }
```

**Response 200**

```json
{
  "accessToken": "eyJ...",
  "refreshToken": "…",
  "expiresIn": 900,
  "user": {
    "id": "…",
    "name": "…",
    "role": "admin",
    "permissions": ["camera.read", "camera.write", "…"]
  }
}
```

`expiresIn` tính bằng **giây** (mặc định 900 = 15 phút).

| Status | Khi nào |
|---|---|
| 401 | Sai username/password |
| 403 | Tài khoản bị tắt |
| 429 | Sai quá 5 lần trong 15 phút |

### `POST /api/v1/auth/refresh_token`

Không cần Bearer. Body:

```json
{ "refreshToken": "…" }
```

Response giống login. Refresh cũ **không dùng lại được**.

**Single session:** đăng nhập máy khác → refresh máy cũ fail `401`.

### `GET /api/v1/auth/get_me`

Cần Bearer. Dùng khi F5 / khôi phục session.

```json
{
  "id": "…",
  "name": "…",
  "role": "operator",
  "permissions": ["camera.read", "zone.control", "…"]
}
```

### `POST /api/v1/auth/logout`

Cần Bearer. Response **204** (không body). Thu hồi refresh phía server. Access cũ vẫn gọi API được tối đa ~15 phút cho tới khi hết hạn.

---

## 3. Camera snapshot

### `GET /api/v1/cameras/get_snapshot?cameraId={id}`

| | |
|---|---|
| Quyền | `camera.read` |
| Response | **Binary** `image/jpeg` (không JSON) |
| Không gian ảnh | Frame infer **640×480 stretch** |

```http
GET /api/v1/cameras/get_snapshot?cameraId=1
Authorization: Bearer …
```

Ví dụ FE (axios):

```ts
const res = await api.get("/api/v1/cameras/get_snapshot", {
  params: { cameraId },
  responseType: "blob",
});
const url = URL.createObjectURL(res.data);
```

| Status | Ý nghĩa |
|---|---|
| 401 / 403 | Token / thiếu quyền |
| 404 | Camera không tồn tại |
| 409 | Camera chưa streaming |
| 503 | Runtime chưa sẵn sàng / chưa có frame |

---

## 4. Zone start / stop

Trạng thái bật/tắt nằm trong **RAM** runtime — **không** ghi Mongo. Restart backend thì về theo `cameras.enabled` trong DB.

### `POST /api/v1/zones/start_zone`

Quyền: `zone.control`

```json
{ "zoneId": "AE5" }
```

**200**

```json
{ "message": "Zone AE5 enabled", "enabled": 1 }
```

`enabled` = số camera đang bật trong runtime (toàn hệ, không chỉ zone đó).

### `POST /api/v1/zones/stop_zone`

Cùng body / quyền. Response tương tự (`message` + `enabled`).

| Status | |
|---|---|
| 503 | Runtime chưa khởi động |

---

## 5. System health + start / stop all

### `GET /api/v1/system/get_health`

Alias chuẩn `/api/v1` của `GET /health`. Cần Bearer (mọi role đã login). Không cần `system.control`.

**200** — healthy:

```json
{
  "status": "ok",
  "service": "AMR Camera System",
  "mongo": true,
  "runtime_running": true,
  "webrtc": { "alive": true, "owned": true, "watchdog": true }
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

> Route cũ `GET /health` vẫn mở (không Bearer) cho probe/ops. FE banner nên gọi `/api/v1/system/get_health`.

Quyền start/stop all: `system.control` (admin).

### `POST /api/v1/system/start_all`

> **Deprecated** — FE mới dùng `POST /api/v1/system/start-cameras` (bật camera **và** inference, xem [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md)). `start_all` chỉ bật camera.

Không body.

**200** (rút gọn)

```json
{
  "message": "Cameras started",
  "total": 2,
  "enabled": 2,
  "streaming": 1,
  "cameras": [ /* status từng cam */ ],
  "warnings": ["cam_1: rtsp timeout"]
}
```

### `POST /api/v1/system/stop_all`

Không body.

```json
{ "message": "All cameras disabled" }
```

| Status | |
|---|---|
| 403 | Thiếu `system.control` |
| 503 | Runtime/model chưa sẵn sàng, hoặc start_all mà không cam nào streaming |

---

## 6. Checklist (đợt 1)

- [ ] Base URL + Swagger `/docs`
- [ ] Lưu 2 token; interceptor refresh khi `401`
- [ ] UI quyền theo `permissions[]`
- [ ] Login xử lý 401 / 403 / 429
- [ ] Snapshot: `responseType: "blob"`
- [ ] Zone id thật (`AE5`)
- [ ] Nút Start/Stop all chỉ khi có `system.control`

Đọc/ghi (cameras, ROI, nodes, pairs…): [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md).
