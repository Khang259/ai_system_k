# Contract FE — Sync cameras → nodes → pairs (SSOT)

> Cập nhật: 2026-10-01  
> **Breaking đầy đủ + checklist FE:** [fe-api-ssot-nodes-pairs.md](./fe-api-ssot-nodes-pairs.md)  
> Auth: Bearer JWT  
> Cây gia phả: **cameras → nodes → pairs**

### Thuật ngữ

| Từ | Nghĩa |
|---|---|
| **SSOT** | Single Source of Truth — camera quyết định node nào thuộc nó + zone của node |
| **observedNodeIds** | Node gắn `camera_id` = camera (API `get_cameras`) |
| **rois keys** | Node đã có box detection trên document camera |
| **Cascade** | Xóa/tắt cha → xóa/tắt con theo cây |
| **Inference pause** | Inference đang tắt (`POST /runtime/pause-scan` hoặc chưa resume) |
| **Replace-set** | `observedNodeIds` = tập đích; id bị bỏ → xóa node (không detach) |

---

## Luật cứng (bắt buộc FE)

1. Workflow cấu hình: **camera → node (observed) → ROI → pair**
2. **1 node ↔ 1 camera** — gắn node đã thuộc camera khác → **409**
3. Gỡ node khỏi `observedNodeIds` = **xóa node** + ROI + **cascade xóa pair** (không còn detach; **không còn** `delete_node`)
4. Disable camera = cascade `enabled=false` trên **nodes + pairs** của camera
5. Xóa camera = cascade xóa toàn bộ nodes + pairs + ROI
6. Tạo/sửa pair: mọi start/end phải **có ROI** trên camera đang gắn; **pair xuyên zone OK**
7. Zone node **chỉ** đổi qua `update_camera.zone` (heritage) — `update_node.zoneId` → **400**
8. Pair **không** có `zoneId` (create/update/list)
9. Mọi API **ghi cấu hình** dưới đây cần **inference đang pause** — nếu đang chạy → **409**

### Inference gate

Trước khi Save / Delete cấu hình:

1. `POST /api/v1/runtime/pause-scan` (cần `system.control`)
2. Gọi API ghi
3. Sau khi xong: `POST /api/v1/runtime/reload` rồi `POST /api/v1/system/start-cameras`
   (gửi robot: `POST /api/v1/runtime/dispatch` — xem [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md))

Message 409 điển hình:  
`Tắt inference trước khi chỉnh cấu hình (pause-scan / stop)`

| API runtime v1 | Quyền |
|---|---|
| `GET /api/v1/runtime/get_status` | Bearer (đã login) |
| `POST /api/v1/runtime/pause-scan` | `system.control` |
| `POST /api/v1/system/start-cameras` | `system.control` |
| `POST /api/v1/runtime/dispatch` | `system.control` |
| `POST /api/v1/runtime/reload` | `system.control` |

| API ghi bị gate | Quyền |
|---|---|
| `PATCH /cameras/update_camera` | `camera.write` |
| `POST /cameras/set_camera_status` | `camera.write` |
| `POST /cameras/delete_camera` | `camera.write` |
| `POST/PATCH/DELETE ROI` | `camera.write` |
| `POST/PATCH pairs/*` ghi | `pair.write` |

**Không gate:** `set_maintenance`, `set_lock`, `unlock` (vận hành runtime).

---

## A. Camera

### `PATCH /api/v1/cameras/update_camera`

```json
{
  "cameraId": 1,
  "observedNodeIds": ["end_10000760"]
}
```

| Hành vi `observedNodeIds` | Kết quả |
|---|---|
| Id mới | Auto-create node (prefix `start_`/`end_`) |
| Id đã thuộc camera này | Giữ / cập nhật zone |
| Id thuộc camera **khác** | **409** |
| Id bị bỏ khỏi list | **Xóa node** + ROI + cascade **pairs** |

**200 extras:**

| Field | Ý nghĩa |
|---|---|
| `observedAssigned` | Số id trong list |
| `observedCreated` | Số node mới tạo |
| `observedRemoved` | Số node bị xóa cascade |
| `observedUnassigned` | Alias = `observedRemoved` (tương thích) |
| `pairsDeleted` | List `start:end` đã xóa |

### `POST /api/v1/cameras/set_camera_status`

```json
{ "cameraId": 1, "enabled": false }
```

Cascade: `cameras.enabled` + mọi node của camera + mọi pair chứa các node đó.

**200:** `{ cameraId, enabled, nodesUpdated, pairsUpdated }`

### `POST /api/v1/cameras/delete_camera`

```json
{ "cameraId": 1 }
```

**200:** `{ cameraId, deleted, nodesDeleted[], pairsDeleted[] }`

---

## B. ROI

### `POST /api/v1/cameras/create_roi`

- Node phải ∈ `observedNodeIds` của đúng `cameraId` — không → **400**
- Cần inference pause

### `POST /api/v1/cameras/delete_roi`

- Xóa ROI → **cascade xóa pair** chứa node đó (node vẫn thuộc camera, chưa có ROI)
- **200:** `{ id, deleted, pairsDeleted[] }`

`observedNodeIds` ≠ `rois` keys:

- observed = đã gắn camera (có thể chưa vẽ ROI)
- rois = đã vẽ box — **bắt buộc trước khi tạo pair**

---

## C. Node

### `POST /api/v1/nodes/delete_node` — **REMOVED**

Dùng `update_camera.observedNodeIds` (replace-set).

### `POST /api/v1/nodes/create_node` — **REMOVED**

Dùng `update_camera.observedNodeIds` / `create_camera`.

### `PATCH /api/v1/nodes/update_node`

Chỉ `priority` / `enabled`. `zoneId` / `cameraId` → **400**.

Ops state vẫn tách:

- `enabled` / `isUnderMaintenance` (+ reason) / `lock.user` / `lock.system`
- `get_pairs` tính `isBlocked` nếu bất kỳ cái nào chặn (kể cả lock)

---

## D. Pair

Xem [fe-api-pairs-crud.md](./fe-api-pairs-crud.md) + [fe-api-ssot-nodes-pairs.md](./fe-api-ssot-nodes-pairs.md).

- Start/end phải gắn camera + **có ROI** → thiếu → **400**
- **Không** `zoneId` trên pair; xuyên zone OK
- Inference pause bắt buộc khi create/update/delete/set_enabled

---

## E. Checklist FE

- [ ] Pipeline UI: Camera Hub → Nodes → ROI coverage → Pairs  
- [ ] Banner + disable Save khi inference đang chạy  
- [ ] Confirm cascade khi gỡ node / xóa camera / disable camera (copy khác nhau)  
- [ ] Dropdown pair chỉ hiện node **đã có ROI**  
- [ ] Không dùng `create_node` / `delete_node`  
- [ ] Không gửi `zoneId` trên pair; không `update_node.zoneId`  
- [ ] Sau ghi cấu hình: refresh cameras / nodes / pairs  
- [ ] Hiển thị `isBlocked` + `blockedReason` từ API  

---

## F. Breaking log

| Trước | Sau |
|---|---|
| Gỡ observed = detach (`camera_id=null`) | Gỡ = **xóa** node + cascade pair |
| `delete_node` tồn tại | **Removed** — chỉ replace-set observed |
| `update_node.zoneId` OK | **400** — zone từ camera |
| Pair có `zoneId` + filter `?zoneId=` | **Bỏ** — pair xuyên zone |
| Pair không cần ROI | **Bắt buộc ROI** |
| Ghi config khi inference chạy | **409** — phải pause |
