# Contract FE — SSOT cameras → nodes → pairs (2026-10)

> Cập nhật: 2026-10-01  
> Thay thế một phần luật cũ trong [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md), [fe-api-camera-node-crud.md](./fe-api-camera-node-crud.md), [fe-api-pairs-crud.md](./fe-api-pairs-crud.md)

Auth: Bearer JWT. Ghi cấu hình cần **inference pause** → `409` nếu đang chạy.

---

## Luật domain (chốt)

| # | Luật |
|---|------|
| 1 | **1 node ↔ 1 camera** bắt buộc (`nodes.camera_id`) |
| 2 | **Pair được xuyên zone** (start/end có thể khác zone) |
| 3 | **Zone node = zone camera** (heritage); FE không sửa zone trên node |
| 4 | **Xóa node chỉ qua** `PATCH /cameras/update_camera` + `observedNodeIds` (replace-set) |
| 5 | Filter `?zoneId=` chỉ còn trên **nodes**; **pairs không filter zone** |

### Thuật ngữ

| Từ | Nghĩa |
|----|--------|
| **SSOT** | Camera quyết định membership + zone của node |
| **observedNodeIds** | Derive từ `nodes.camera_id` lúc đọc; ghi = replace-set |
| **Replace-set** | Body là tập đích; id bị bỏ khỏi list → cascade xóa node + ROI + pairs |
| **Heritage zone** | `nodes.zone_id` chỉ BE ghi khi create/gán/đổi zone camera |

---

## Breaking changes (FE phải đổi)

| Trước | Sau |
|-------|-----|
| `POST /nodes/delete_node` | **Removed** — 404 |
| UI nút “Xóa” trên Node list | **Bỏ** — xóa qua form Camera (`observedNodeIds`) |
| `PATCH /nodes/update_node` + `zoneId` | **400** — message cấm zoneId |
| `PATCH /nodes/update_node` + `cameraId` | **400** (như cũ, message rõ hơn) |
| `GET /pairs/get_pairs?zoneId=` | Query **bỏ** — luôn trả toàn bộ |
| Pair response / create / update có `zoneId` | **Không còn** field `zoneId` |
| `POST /pairs/create_pair` bắt buộc `zoneId` | **Không gửi** `zoneId` |
| `PATCH /pairs/update_pair` + `zoneId` | **400** |

---

## A. Xóa / tạo / gán node

### Chỉ một cửa ghi membership

`PATCH /api/v1/cameras/update_camera` (hoặc `POST .../create_camera` kèm `observedNodeIds`)

```json
{
  "cameraId": 1,
  "observedNodeIds": ["start_10000059", "end_10000061"]
}
```

| Hành vi | Kết quả |
|---------|---------|
| Id mới (`start_*` / `end_*`) | Tạo node + gắn `camera_id` + `zone_id` = zone cam |
| Id đã thuộc cam này | Giữ / sync zone |
| Id thuộc cam khác | **409** |
| Id bị bỏ khỏi list | **Xóa** node + ROI + cascade **mọi pair** chứa node |

**Không còn** `POST /api/v1/nodes/delete_node`.

Xóa nhiều node cùng lúc = gửi list còn lại (một request).

Confirm UI: cascade xóa pair khi gỡ chip node trên Camera hub.

---

## B. Node — update còn lại

### `PATCH /api/v1/nodes/update_node`

Cho phép:

```json
{ "nodeId": "start_10000060", "priority": 5, "enabled": false }
```

| Field | |
|-------|--|
| `priority` | OK |
| `enabled` | OK (tắt điểm vận hành; không cascade pair) |
| `zoneId` | **Cấm** → 400 |
| `cameraId` | **Cấm** → 400 |

Đổi zone node: `PATCH /cameras/update_camera` `{ "cameraId", "zone": "AE6" }` → BE cascade `nodes.zone_id`.

### `GET /api/v1/nodes/get_nodes?zoneId=`

Vẫn hỗ trợ. `zoneId` trên item = mirror từ camera (BE ghi).

Ops không đổi: `set_maintenance`, `set_lock`, `unlock`.

---

## C. Pair — không còn zone

### `GET /api/v1/pairs/get_pairs`

Không query `zoneId`. Item **không** có `zoneId`:

```json
{
  "id": "start_10000060:end_10000760",
  "name": "…",
  "startNodeId": "start_10000060",
  "endNodeId": "end_10000760",
  "pairType": "normal",
  "enabled": true,
  "autoDispatch": true,
  "isBlocked": false,
  "blockedReason": null
}
```

FE cần filter theo zone: lấy `zoneId` từ `get_nodes` (hoặc camera) theo `startNodeId` / `endNodeId`.

### `POST /api/v1/pairs/create_pair`

```json
{
  "startNodeId": "start_10000060",
  "endNodeId": "end_10000760",
  "pairType": "normal",
  "enabled": true,
  "autoDispatch": true,
  "name": "Line 1"
}
```

Không gửi `zoneId`. Start/end có thể khác zone (mỗi node heritage cam của nó).

Vẫn bắt buộc: node gắn camera + có ROI; inference pause; trùng → 409.

### `PATCH /api/v1/pairs/update_pair`

Cho phép: `startNodeId`, `endNodeId`, `pairType`, `enabled`, `autoDispatch`, `name`.  
Gửi `zoneId` → **400**.

---

## D. Checklist FE

- [ ] Bỏ nút / API `delete_node`
- [ ] Xóa node chỉ qua Camera form `observedNodeIds` (gửi **full list** còn lại)
- [ ] Bỏ gửi / hiển thị `zoneId` trên pair CRUD + list
- [ ] Bỏ `?zoneId=` trên `get_pairs`
- [ ] Filter zone cho pair (nếu UI cần) = join từ nodes/cameras
- [ ] `update_node` không gửi `zoneId` / `cameraId`
- [ ] Đổi zone điểm = đổi zone **camera** cha
- [ ] Confirm cascade khi gỡ observed / xóa camera / disable camera
- [ ] Xử lý 400 message mới (zoneId cấm trên node/pair)

---

## E. Migrate DB (ops)

```text
.venv\Scripts\python.exe scripts/migrate_ssot_nodes_pairs.py --dry-run
.venv\Scripts\python.exe scripts/migrate_ssot_nodes_pairs.py
```

- Xóa orphan node (`camera_id` null / cam không tồn tại) + pairs + ROI keys  
- Sync `nodes.zone_id` từ camera  
- `$unset pairs.zone_id`
