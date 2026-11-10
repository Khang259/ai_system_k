# Contract FE — Update camera + CRUD node

> Cập nhật: 2026-10-02  
> **Luật sync đầy đủ:** [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md)  
> **Breaking SSOT:** [fe-api-ssot-nodes-pairs.md](./fe-api-ssot-nodes-pairs.md)  
> **Tạo camera:** [fe-api-create-camera.md](./fe-api-create-camera.md)  
> **Start priority:** [fe-api-start-priority.md](./fe-api-start-priority.md)

Auth: Bearer + `camera.write` (trừ khi ghi chú khác).

### Ghi chú sản phẩm

- Cây: **cameras → nodes → pairs** (camera SSOT identity).
- Tạo camera: `POST /api/v1/cameras/create_camera`.
- Tạo / gán / **xóa** node: `PATCH /api/v1/cameras/update_camera` + `observedNodeIds` (replace-set).
- Tạo **start mới** cần `nodePriorities` — xem [fe-api-start-priority.md](./fe-api-start-priority.md).
- `POST /nodes/create_node`, `POST /nodes/delete_node`: **không dùng** (delete đã remove).
- Zone node chỉ đổi qua `update_camera.zone`.
- Ghi cấu hình cần **inference pause** → 409 nếu đang chạy.

---

## A. Camera

### `POST /api/v1/cameras/create_camera`

Chi tiết: [fe-api-create-camera.md](./fe-api-create-camera.md).

### `PATCH /api/v1/cameras/update_camera`

```json
{
  "cameraId": 1,
  "name": "MOCK-CAM-001",
  "rtspUrl": "rtsp://127.0.0.1:8554/cam_1",
  "zone": "AE5",
  "observedNodeIds": ["start_10000060", "end_10000760"],
  "nodePriorities": {
    "start_10000060": 1
  }
}
```

`nodePriorities` chỉ bắt buộc khi **tạo mới** `start_*` trong `observedNodeIds`. Chi tiết lỗi `400`/`409`: [fe-api-start-priority.md](./fe-api-start-priority.md).

| Field | Side-effect |
|---|---|
| `name` / `rtspUrl` / `zone` | Zone cascade `nodes.zone_id`; đổi zone có thể **409** nếu priority start trùng zone đích; **`rtspUrl` unique** (trùng cam khác → **409**) |
| `observedNodeIds` | Sync: create / gán; **gỡ = xóa node + ROI + cascade pairs**; node thuộc camera khác → **409** |
| `nodePriorities` | Map priority khi tạo start mới — [fe-api-start-priority.md](./fe-api-start-priority.md) |

**200 extras:** `observedAssigned`, `observedCreated`, `observedRemoved`, `pairsDeleted`, `observedUnassigned` (= removed).

### `POST /api/v1/cameras/set_camera_status`

Cascade disable/enable nodes + pairs. Cần inference pause.

### `POST /api/v1/cameras/delete_camera`

```json
{ "cameraId": 1 }
```

Cascade xóa nodes + pairs. **200:** `{ deleted, nodesDeleted[], pairsDeleted[] }`

---

## B. Node

### `GET /api/v1/nodes/get_nodes?zoneId=` (optional)

Vẫn filter theo zone (mirror từ camera).

### `PATCH /api/v1/nodes/update_node`

Cho phép: `priority`, `enabled`.  
**Cấm:** `zoneId`, `cameraId` → **400**.  
Start đổi `priority` trùng trong zone → **409**. Đổi priority chỉ ảnh hưởng dispatch sau **restart runtime**.  
Chi tiết: [fe-api-start-priority.md](./fe-api-start-priority.md).

### Xóa node

**Không còn** `POST /api/v1/nodes/delete_node`.  
Dùng `update_camera` + `observedNodeIds` = list còn lại.
