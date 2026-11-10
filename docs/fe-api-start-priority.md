# Contract FE — Start priority (dispatch + CRUD)

> Cập nhật: 2026-10-02  
> Liên quan: [fe-api-create-camera.md](./fe-api-create-camera.md), [fe-api-camera-node-crud.md](./fe-api-camera-node-crud.md), [fe-api-ssot-nodes-pairs.md](./fe-api-ssot-nodes-pairs.md)

Auth: Bearer. Ghi camera/node cần quyền `camera.write` + **inference pause** → `409` nếu inference đang chạy (trừ `update_node` chỉ đổi field DB — vẫn audit như các API ghi khác).

---

## Luật domain (chốt)

| # | Luật |
|---|------|
| 1 | Thứ tự gửi ICS chỉ theo field Mongo **`priority`** của **start** (không còn lấy số từ `node_id`) |
| 2 | **Số nhỏ gửi trước** (`1` trước `2`) |
| 3 | **`priority` unique trong từng `zone`** — chỉ áp dụng **start** |
| 4 | Hai zone khác nhau **được phép** cùng số `priority` (vd. A=1 và B=1) |
| 5 | Cùng `priority` khác zone cùng ready → thứ tự ICS **không quan trọng** (BE tie-break kỹ thuật) |
| 6 | Tạo **start mới** → **bắt buộc** gửi `nodePriorities[nodeId]` |
| 7 | **End** không bắt buộc priority; không unique |
| 8 | Đổi `priority` trên DB chỉ ảnh hưởng dispatch sau **restart runtime** |

### Thuật ngữ

| Từ | Nghĩa |
|----|--------|
| **priority** | Số nguyên `>= 0` trên document node — hạng ưu tiên start trong zone |
| **nodePriorities** | Map `nodeId → priority` khi create/gán node mới qua camera API |
| **Unique theo zone** | Không hai start cùng `zone_id` + cùng `priority` |
| **Hydrate** | Runtime nạp map priority lúc start; đổi priority lúc runtime đang chạy → cần restart |

---

## Breaking changes (FE phải đổi)

| Trước | Sau |
|-------|-----|
| Tạo start qua `create_camera` / `update_camera` không cần priority (BE gán `999`) | **Start mới** thiếu `nodePriorities[id]` → **`400`** |
| Nhiều start cùng zone cùng `priority` (vd. toàn `999`) | **`409`** khi tạo/sửa trùng trong zone |
| Dispatch sort theo digits trong `node_id` | Sort theo Mongo `priority` (sau migrate + restart) |
| Đổi priority qua `update_node` là đủ cho hàng đợi ngay | Vẫn ghi Mongo; **dispatch chỉ đúng sau restart runtime** |

---

## A. `POST /api/v1/cameras/create_camera`

Thêm field tùy chọn `nodePriorities`.  
**Khi `observedNodeIds` có `start_*` chưa tồn tại** → mỗi start đó **phải** có entry trong `nodePriorities`.

### Request

```json
{
  "name": "AE5-CAM-06",
  "rtspUrl": "rtsp://host/stream",
  "zone": "AE5",
  "observedNodeIds": ["start_10000099", "end_10000799"],
  "nodePriorities": {
    "start_10000099": 3
  }
}
```

| Field | Bắt buộc | Mô tả |
|-------|----------|--------|
| `name` / `rtspUrl` / `zone` / `observedNodeIds` | Như [fe-api-create-camera.md](./fe-api-create-camera.md) | Không đổi |
| `nodePriorities` | Có **nếu** tạo mới ít nhất một `start_*` | Object: key = `nodeId`, value = int `>= 0` |
| `nodePriorities` cho `end_*` | Không | Có thì BE lưu; không có → end mặc định `0` |

### Response `200`

Như create camera hiện tại (`cameraId`, `observedCreated`, `requiresRestart`, …).  
Node start mới có `priority` đúng giá trị đã gửi.

### Lỗi liên quan priority

| HTTP | Khi nào | `message` (ví dụ) |
|------|---------|-------------------|
| `400` | Tạo `start_*` mới thiếu key trong `nodePriorities` | `start start_10000099 cần nodePriorities["start_10000099"]` |
| `400` | `priority < 0` | `priority phải >= 0` |
| `409` | Trùng priority với start khác **cùng zone** (DB hoặc trong cùng batch) | `priority 3 đã dùng bởi start start_xxx trong zone AE5` |

Gán node **đã tồn tại** (chỉ đổi `camera_id` / zone) → **không** bắt buộc lại `nodePriorities`.

---

## B. `PATCH /api/v1/cameras/update_camera`

Cùng field `nodePriorities` — chỉ cần khi body `observedNodeIds` **tạo mới** các `start_*` chưa có trong DB.

```json
{
  "cameraId": 1,
  "observedNodeIds": [
    "start_10000060",
    "end_10000760",
    "start_10000999"
  ],
  "nodePriorities": {
    "start_10000999": 2
  }
}
```

| Side-effect | Chi tiết |
|-------------|----------|
| Tạo start mới | Cần `nodePriorities`; unique trong zone camera |
| Đổi `zone` camera | Cascade `nodes.zone_id`; nếu start của cam mang `priority` đã có ở zone đích → **`409`** (trước khi ghi) |
| Gỡ id khỏi `observedNodeIds` | Cascade xóa node như SSOT (không đổi) |

Inference pause + lỗi `rtspUrl` / ownership node: như contract camera cũ.

---

## C. `PATCH /api/v1/nodes/update_node`

Sửa `priority` / `enabled`. Không đổi `cameraId` / `zoneId`.

### Request

```json
{
  "nodeId": "start_10000060",
  "priority": 2
}
```

| Field | Bắt buộc | Mô tả |
|-------|----------|--------|
| `nodeId` | Có | |
| `priority` | Một trong hai | int `>= 0`; start → check unique trong zone hiện tại |
| `enabled` | Một trong hai | bool |
| `zoneId` / `cameraId` | Cấm | Gửi → `400` |

### Response `200`

Item node (camelCase), gồm `priority`, `label`, `zoneId`, `lock`, …

### Lỗi

| HTTP | Khi nào |
|------|---------|
| `400` | Không có `priority`/`enabled`; hoặc gửi `zoneId`/`cameraId`; hoặc `priority < 0` |
| `404` | Node không tồn tại |
| `409` | Start đổi sang `priority` đã thuộc start khác **cùng zone** |

### FE UX

Sau `update_node` đổi priority thành công: hiện toast / banner **cần restart runtime** để thứ tự dispatch đổi.  
`requiresRestart` **không** trả trên API này — FE tự biết theo luật domain #8.

---

## D. `GET /api/v1/nodes/get_nodes`

Không breaking shape. FE dùng `priority` + `zoneId` để:

- Hiển thị hạng / label (`S-01`… từ `priority`)
- Form chọn priority khi tạo start (tránh trùng trong zone — có thể pre-check bằng list này; BE vẫn là nguồn chặn cuối)

```json
{
  "items": [
    {
      "id": "start_10000060",
      "nodeId": "start_10000060",
      "label": "S-01",
      "kind": "start",
      "zoneId": "AE5",
      "cameraId": 1,
      "priority": 1,
      "enabled": true,
      "isUnderMaintenance": false,
      "maintenanceReason": null,
      "lock": { "user": false, "system": false, "orderId": null }
    }
  ]
}
```

---

## E. Hành vi dispatch (FE hiểu để QA)

```text
ready starts → sort (priority ASC, zoneId, nodeId) → ghép pair → POST ICS
```

| Case | Kỳ vọng |
|------|---------|
| Zone AE5: start p=1 và p=2 cùng ready | Gửi p=1 trước |
| Zone A p=1 và Zone B p=1 cùng ready | Cả hai đều gửi được; ai trước **không** cần assert nghiệp vụ |
| Đổi priority khi runtime đang chạy | Mongo đã mới; hàng đợi ICS **chưa** đổi đến khi restart |

---

## F. Checklist tích hợp FE

1. Form **Create / Update camera**: khi thêm `start_*` mới → bắt buộc input priority + gửi `nodePriorities`.
2. Validate client: `priority >= 0`; cảnh báo nếu trùng start cùng zone trong list đang mở (BE vẫn `409`).
3. Form **Update node**: đổi priority → xử lý `409`; sau success nhắc **restart runtime**.
4. Không gửi `zoneId`/`cameraId` trên `update_node`.
5. End node: không bắt buộc priority trên UI create (optional).
6. QA: sau migrate data + deploy + restart, thứ tự dispatch theo `priority` Mongo.

---

## G. Ops / migrate (không phải API FE)

Trước/đồng thời deploy:

```bash
.venv\Scripts\python.exe scripts/migrate_start_priority_per_zone.py --dry-run
.venv\Scripts\python.exe scripts/migrate_start_priority_per_zone.py
.venv\Scripts\python.exe scripts/migrate_start_priority_per_zone.py --ensure-index
```

Script gán lại `1..N` cho mọi start **trong từng zone** (theo digits `node_id` cũ).  
Thiếu bước này + bật validation → create/update dễ `409` vì data cũ nhiều `999`.
