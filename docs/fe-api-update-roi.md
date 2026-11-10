# Contract FE — Update ROI (batch)

> Cập nhật: 2026-09-14  
> Endpoint: **`PATCH /api/v1/cameras/update_roi`**  
> Luật đồng bộ camera / node / ROI / pair: [fe-api-sync-camera-node-pair.md](./fe-api-sync-camera-node-pair.md).

---

## 1. Quy ước

| | |
|---|---|
| Method + path | `PATCH /api/v1/cameras/update_roi` |
| Auth | `Authorization: Bearer <accessToken>` |
| Quyền | `camera.write` |
| Body | JSON camelCase |
| Thành công | **200** — `{ "items": [ ...ROI ] }` |
| Lỗi | HTTP status thật + `{ "message": "..." }` — **không ghi** nếu 1 item lỗi |

**ROI** = vùng chữ nhật trên frame, gắn 1 **node**.  
**`box`** = `[x, y, w, h]` trong khung **640×480**.

Khác `create_roi`: mỗi item phải **đã tồn tại** trong Mongo → thiếu key thì **404** cả batch.

---

## 2. Request (batch — khuyến nghị)

```json
{
  "items": [
    { "id": "1:start_10000060", "box": [90, 120, 140, 90] },
    { "id": "1:start_10000059", "box": [240, 120, 140, 90] },
    { "cameraId": 1, "nodeId": "end_10000760", "box": [80, 280, 140, 90] },
    { "cameraId": 1, "nodeId": "end_10000761", "box": [240, 280, 140, 90] }
  ]
}
```

Mỗi phần tử trong `items`:

| Field | Bắt buộc | Ý nghĩa |
|---|---|---|
| `box` | Có | `[x, y, w, h]` — đúng 4 số |
| `id` | Một trong hai | `"{cameraId}:{nodeId}"` |
| `cameraId` + `nodeId` | Một trong hai | Khi không gửi `id` |

Validate từng `box`: `x,y ≥ 0`, `w,h > 0`, `x+w ≤ 640`, `y+h ≤ 480`.

### Single (tương thích cũ)

Vẫn nhận body 1 ROI — server tự bọc thành `items` 1 phần tử:

```json
{ "id": "1:start_10000060", "box": [90, 120, 140, 90] }
```

---

## 3. Response 200

```json
{
  "items": [
    {
      "id": "1:start_10000060",
      "cameraId": 1,
      "nodeId": "start_10000060",
      "label": "S-01",
      "kind": "start",
      "box": [90, 120, 140, 90],
      "refWidth": 640,
      "refHeight": 480
    }
  ]
}
```

Số phần tử `items` response = số phần tử request đã ghi thành công.

### Mongo

Mỗi key `rois.{nodeId}` được `$set`:

```json
{
  "roi": [90, 120, 140, 90],
  "start": true,
  "end": false,
  "ref_width": 640,
  "ref_height": 480
}
```

---

## 4. Lỗi (fail trước khi ghi)

Validate **toàn bộ** `items` trước; lỗi 1 item → **không** update item nào.

| HTTP | Khi nào | `message` (ví dụ) |
|---|---|---|
| **400** | `items` rỗng / thiếu định danh / `box` sai | `"items[0]: box vượt khung 640×480"` |
| **401** | Thiếu / sai Bearer | `"Thiếu Bearer token"` |
| **403** | Không có `camera.write` | `"Thiếu quyền: camera.write"` |
| **404** | Camera hoặc ROI chưa tồn tại | `"items[1]: ROI không tồn tại (1:missing)"` |
| **422** | Body không parse được (thiếu `items` và `box`) | Pydantic validation |

---

## 5. Ví dụ

```http
PATCH /api/v1/cameras/update_roi HTTP/1.1
Authorization: Bearer <accessToken>
Content-Type: application/json

{
  "items": [
    { "id": "1:start_10000060", "box": [90, 120, 140, 90] },
    { "id": "1:end_10000760", "box": [80, 280, 140, 90] }
  ]
}
```

```bash
curl -X PATCH "http://127.0.0.1:8000/api/v1/cameras/update_roi" ^
  -H "Authorization: Bearer <accessToken>" ^
  -H "Content-Type: application/json" ^
  -d "{\"items\":[{\"id\":\"1:start_10000060\",\"box\":[90,120,140,90]},{\"id\":\"1:end_10000760\",\"box\":[80,280,140,90]}]}"
```

---

## 6. Gợi ý FE

1. Màn chỉnh ROI camera: gom mọi box đã đổi → **một** `PATCH` với `items`.
2. Lấy `id` từ `GET /api/v1/cameras/get_rois?cameraId=`.
3. ROI chưa có trên camera → `POST /create_roi` trước (hoặc tạo từng cái), rồi mới batch update.
4. Response luôn đọc `data.items` (kể cả khi chỉ gửi 1 ROI).
