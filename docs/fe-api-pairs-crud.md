# Contract FE — CRUD pair (xuyên zone)

> Cập nhật: 2026-10-01  
> Prefix: `/api/v1/pairs/*`  
> **Luật sync + ROI + inference gate:** [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md)  
> **Breaking SSOT:** [fe-api-ssot-nodes-pairs.md](./fe-api-ssot-nodes-pairs.md)

Auth: Bearer JWT

| Quyền | Endpoint |
|---|---|
| `pair.read` | `GET /get_pairs` |
| `pair.write` | create / update / delete / set_enabled |

Sau mọi thao tác ghi: **reload runtime** (`runtimeReloaded: true`).  
Ghi khi inference đang chạy → **409**.

**Pair không thuộc một zone** — start/end có thể khác zone (heritage từng camera).

---

## 1. Danh sách

### `GET /api/v1/pairs/get_pairs`

Không còn `?zoneId=`. Response **không** có `zoneId`.

`isBlocked` khi: pair/node disabled, maintenance, hoặc `lock.user` / `lock.system`.

Filter theo zone phía FE: join `startNodeId`/`endNodeId` → `get_nodes` / cameras.

---

## 2. Tạo pair

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

**Không gửi `zoneId`.**

| Rule | HTTP |
|---|---|
| Node gắn camera + **có ROI** | 400 nếu thiếu |
| `pairType=normal` cần `endNodeId` | 400 |
| Trùng cặp | 409 |
| Inference đang chạy | 409 |

Empty: `{ "startNodeId", "pairType": "empty" }`

---

## 3. Update / delete / set_enabled

- `PATCH /update_pair` — partial: start / end / pairType / enabled / autoDispatch / name  
  - Gửi `zoneId` → **400**
  - Đổi start/end/type → validate ROI lại  
- `POST /delete_pair` — `{ "id" }` hoặc start/end  
- `POST /set_pair_enabled` — `{ "id", "enabled" }`  

Tất cả cần inference pause.

---

## Checklist FE

- [ ] Bỏ `zoneId` khỏi form / type pair  
- [ ] Bỏ filter `?zoneId=` trên get_pairs  
- [ ] Dropdown pair chỉ node đã có ROI  
- [ ] Xử lý 409 inference / 400 thiếu ROI / 400 zoneId cấm  
- [ ] Refresh list sau ghi + cascade từ camera  
