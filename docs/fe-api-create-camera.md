# Contract FE — Create camera

> Cập nhật: 2026-10-02  
> Liên quan: [fe-api-camera-node-crud.md](./fe-api-camera-node-crud.md), [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md), [fe-api-ssot-nodes-pairs.md](./fe-api-ssot-nodes-pairs.md), [fe-api-start-priority.md](./fe-api-start-priority.md)

Auth: Bearer + `camera.write`.

Ghi cấu hình cần **inference pause** → `409` nếu inference đang chạy.

---

## `POST /api/v1/cameras/create_camera`

Tạo camera mới. `cameraId` do BE cấp (`max(existing) + 1`).

### Request

```json
{
  "name": "AE5-CAM-06",
  "rtspUrl": "rtsp://host/stream",
  "zone": "AE5",
  "observedNodeIds": ["start_10000060"],
  "nodePriorities": {
    "start_10000060": 1
  }
}
```

| Field | Bắt buộc | Mô tả |
|-------|----------|--------|
| `name` | Có | Tên hiển thị (không rỗng sau trim) |
| `rtspUrl` | Có | URL RTSP (không rỗng sau trim). **Unique** giữa mọi camera → trùng → `409` |
| `zone` | Không | Zone id — BE upper-case (`ae5` → `AE5`). Gửi `""` → `400` |
| `observedNodeIds` | Không | Node `start_*` / `end_*`. Có list thì **bắt buộc** có `zone` |
| `nodePriorities` | Có nếu tạo mới `start_*` | Map `nodeId → priority` (`>= 0`). Chi tiết: [fe-api-start-priority.md](./fe-api-start-priority.md) |

### Response `200`

Data **trần** (không bọc `success`). Ví dụ:

```json
{
  "cameraId": 6,
  "name": "AE5-CAM-06",
  "rtspUrl": "rtsp://host/stream",
  "zone": "AE5",
  "status": "offline",
  "resolution": "640x480",
  "mapPosition": null,
  "observedNodeIds": ["start_10000060"],
  "enabled": true,
  "error": null,
  "requiresRestart": true,
  "observedAssigned": 1,
  "observedCreated": 1
}
```

| Field | Nghĩa |
|-------|--------|
| `cameraId` | Id mới (auto) |
| `status` | Luôn `"offline"` ngay sau create (chưa có trong runtime) |
| `requiresRestart` | `true` nếu runtime đang chạy → FE nên gọi reload / nhắc restart để nhận cam |
| `observedCreated` | Số node **mới tạo** |
| `observedAssigned` | Số node gán vào cam (= created + assign node đã tồn tại chưa thuộc cam khác) |

### Lỗi — `rtspUrl` trùng

Khi `rtspUrl` (sau trim) đã thuộc camera khác:

| | |
|---|---|
| **HTTP** | `409 Conflict` |
| **Body** | `{ "message": "rtspUrl đã dùng bởi camera {cameraId}" }` |

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{
  "message": "rtspUrl đã dùng bởi camera 1"
}
```

| Phần | FE dùng |
|------|---------|
| `status_code === 409` | Conflict — không tạo được |
| `message` | Hiện toast / form error; `{cameraId}` = cam đang giữ URL đó |

Cùng rule trên `PATCH /api/v1/cameras/update_camera` khi đổi sang URL đang dùng bởi cam khác (giữ nguyên URL của chính mình → OK).

### Lỗi thường gặp khác

| HTTP | `message` (ví dụ) | Khi nào |
|------|-------------------|---------|
| `400` | `name không được rỗng` / `rtspUrl không được rỗng` / … | Validate field |
| `400` | `start … cần nodePriorities["…"]` | Tạo start mới thiếu priority — [fe-api-start-priority.md](./fe-api-start-priority.md) |
| `409` | *(message inference pause)* | Inference đang chạy |
| `409` | `rtspUrl đã dùng bởi camera {id}` | RTSP trùng — xem trên |
| `409` | `priority N đã dùng bởi start … trong zone …` | Priority trùng trong zone |
| `409` | `Node {id} đang thuộc camera {id} (1 node chỉ gắn 1 camera)` | Node conflict |

Lỗi luôn dạng `{ "message": "..." }` (xem [fe-api-responses-status.md](./fe-api-responses-status.md)).

### Side-effect `observedNodeIds`

- Node chưa có → tạo mới (`enabled: true`); **start bắt buộc** `nodePriorities`; end mặc định `priority: 0` nếu không gửi
- Node đã có, chưa thuộc cam khác → gán lại `camera_id` + `zone_id` (không bắt buộc lại priority)
- Node thuộc cam khác → `409`, **không** tạo camera

### Ví dụ tối thiểu

```json
{
  "name": "AE5-CAM-06",
  "rtspUrl": "rtsp://host/stream"
}
```

→ `zone: ""`, `observedNodeIds: []`.
