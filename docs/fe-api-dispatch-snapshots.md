# Contract FE — Snapshot khi dispatch Single

> Cập nhật: **2026-10-08**  
> Liên quan: [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md), [fe-api-active-tasks.md](./fe-api-active-tasks.md), [fe-api-system-action-logs.md](./fe-api-system-action-logs.md)

Auth: Bearer JWT + quyền **`logs.read`**.

---

## Mục tiêu

Sau khi BE gửi ICS **Single** thành công, FE có thể hiện ảnh pair (start|end ghép ngang) gắn với `orderId` — dùng cho panel lệnh / chi tiết lịch sử.

**Thuật ngữ**

| Từ | Nghĩa |
|----|--------|
| **Snapshot** | JPEG (+ JSON sidecar) ghi lúc dispatch OK |
| **capture** | Chốt frame GPU/placeholder **trước** gửi ICS |
| **save** | Ghi đĩa **sau** ICS success |
| **`imagePath`** | Chỉ **basename** file trong `SNAPSHOT_DIR` (không path tuyệt đối) |
| **`ENABLE_SNAPSHOTS`** | Công tắc BE (`.env` / settings). Tắt → không tạo store, không ghi ảnh |

---

## Phạm vi hiện tại

| Strategy | Snapshot |
|----------|----------|
| **Single** | **Có** — capture → ICS → save + index Mongo |
| Empty / Double / overflow | **Chưa** (TODO trong `dispatch_service`) |

Sandbox: không có video thật → BE ghi **ảnh placeholder** (nền xanh + ROI giả) để FE vẫn tích hợp được.

Production: frame lấy từ camera runtime (`capture_for_node`).

---

## Luồng BE (Single)

```
PairManager → dispatch_single
  1) capture_pair(start, end)     # nếu ENABLE_SNAPSHOTS
  2) ICS gateway.send(...)
  3) nếu success → save_pair_snapshots(...) + Mongo indexer
```

Tên file (gợi ý parse, không phụ thuộc cứng):

```text
{orderIdSanitized}_{startNodeId}-{endNodeId}_{YYYYMMDD_HHMMSS_ffffff}.jpg
```

Cùng basename có `.json` sidecar (meta detections/ROI) — FE **không** cần đọc JSON trừ khi debug.

Mongo collection `snapshots` (mỗi node một bản ghi): `order_id`, `node_id`, `node_type`, `zone_id`, `image_path`, …

---

## API

### `GET /api/v1/snapshots/get_by_order`

Lấy meta theo `orderId` → FE lấy `imageUrl` rồi tải JPEG.

```http
GET /api/v1/snapshots/get_by_order?orderId=S-10000060-10000061-20261008120000
Authorization: Bearer <access_token>
```

#### Response `200`

```json
{
  "orderId": "S-10000060-10000061-20261008120000",
  "items": [
    {
      "orderId": "S-10000060-10000061-20261008120000",
      "nodeId": "start_10000060",
      "nodeType": "start",
      "zoneId": "A",
      "imagePath": "S-10000060-10000061-20261008120000_start_10000060-end_10000061_20261008_120001_123456.jpg",
      "imageUrl": "/api/v1/snapshots/get_image?file=S-10000060-10000061-20261008120000_start_10000060-end_10000061_20261008_120001_123456.jpg",
      "decision": "auto",
      "createdAt": "2026-10-08T05:00:01+00:00"
    },
    {
      "orderId": "S-10000060-10000061-20261008120000",
      "nodeId": "end_10000061",
      "nodeType": "end",
      "zoneId": "A",
      "imagePath": "S-10000060-10000061-20261008120000_start_10000060-end_10000061_20261008_120001_123456.jpg",
      "imageUrl": "/api/v1/snapshots/get_image?file=…",
      "decision": "auto",
      "createdAt": "2026-10-08T05:00:01+00:00"
    }
  ]
}
```

| Field | Type | Mô tả |
|-------|------|--------|
| `items` | `array` | Rỗng nếu chưa ghi / chưa index / `ENABLE_SNAPSHOTS=false` |
| `imagePath` | `string` | Basename — truyền vào `get_image` |
| `imageUrl` | `string \| null` | Path relative API (ghép `apiOrigin` trên FE) |
| `nodeType` | `string` | `start` \| `end` |

> Single thường ghi **một JPEG ghép ngang**; cả start và end trỏ **cùng** `imagePath`.

#### Lỗi

| HTTP | Ý nghĩa |
|------|---------|
| `400` | Thiếu `orderId` |
| `401` / `403` | Auth / thiếu `logs.read` |

---

### `GET /api/v1/snapshots/get_image`

Trả raw JPEG (không envelope JSON).

```http
GET /api/v1/snapshots/get_image?file=<basename.jpg>
Authorization: Bearer <access_token>
```

| HTTP | Body | Ý nghĩa |
|------|------|---------|
| `200` | `image/jpeg` bytes | OK |
| `400` | `{ "message": "…" }` | Tên file không hợp lệ / không phải ảnh |
| `404` | `{ "message": "Snapshot không tồn tại hoặc đã hết hạn" }` | Đã dọn retention / chưa ghi |
| `401` / `403` | | Auth |

**Không** chấp nhận path (`../`, thư mục con). Chỉ basename trong `SNAPSHOT_DIR`.

---

## Tích hợp FE gợi ý

| UI | Cách |
|----|------|
| Panel active task / chi tiết lệnh | Sau có `orderId` → `get_by_order` → `<img src="{apiOrigin}{imageUrl}">` (kèm Bearer qua blob/fetch nếu img tag không gửi header) |
| Notification có `snapshotImageUrl` | Dùng trực tiếp field từ `get_notifications` (nếu BE gắn `snapshot_file`) |
| ICS fail | **Không** có snapshot (chỉ save khi success) |

**Bearer trên `<img>`:** trình duyệt không gửi `Authorization` cho thẻ img. FE nên:

1. `fetch(imageUrl, { headers: { Authorization: Bearer … }})` → `blob:` URL, hoặc  
2. Proxy qua FE BFF.

Poll: gọi `get_by_order` sau SSE `dispatch.task` (issued) — index Mongo fire-and-forget, có thể trễ vài trăm ms; retry ngắn nếu `items=[]`.

---

## Cấu hình BE

| Env | Default | Ghi chú |
|-----|---------|---------|
| `ENABLE_SNAPSHOTS` | `true` | `false` → tắt hoàn toàn |
| `SNAPSHOT_DIR` | `snapshots` | Thư mục JPEG trên disk |
| `SNAPSHOT_QUALITY` | `85` | JPEG quality |

Reload runtime sau khi đổi flag (`POST /api/v1/runtime/reload` hoặc restart app).

---

## Checklist FE

- [ ] Sau dispatch Single OK: gọi `get_by_order` theo `orderId`
- [ ] Render ảnh qua fetch+blob (có Bearer) hoặc BFF
- [ ] Xử lý `404` = ảnh hết hạn / chưa sẵn
- [ ] Không giả định Empty/Double có snapshot
- [ ] Sandbox: chấp nhận ảnh placeholder (không phải video thật)

---

## Không làm (đợt này)

- List snapshot toàn hệ / filter zone trên API riêng  
- SSE đẩy URL ảnh (FE poll `get_by_order`)  
- Snapshot cho Empty / Double  
