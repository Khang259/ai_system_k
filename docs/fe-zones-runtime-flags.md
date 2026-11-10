# FE — Zone runtime flags (`isRunning` / `isStreaming`)

Tài liệu tích hợp badge / trạng thái fleet từ zone API.

## Endpoint

| Method | Path | Quyền |
|--------|------|--------|
| `GET` | `/api/v1/zones/get_zones` | `CAMERA_READ` |
| `GET` | `/api/v1/poll` (`include=zones`) | cùng auth poll |

Cả hai trả cùng nghĩa field (poll chỉ forward subset).

### Shape zone item (`get_zones`)

```json
{
  "id": "AE5",
  "name": "Khu AE5",
  "isRunning": true,
  "isStreaming": false,
  "isConfigEnabled": true,
  "cameraCount": 19,
  "nodeCount": 40,
  "lastChangedAt": null,
  "lastChangedBy": null
}
```

Poll `zones.items[]` có: `id`, `isRunning`, `isStreaming`, `isConfigEnabled`, `cameraCount`, `nodeCount`.

---

## Contract field

| Field | Nguồn | Nghĩa |
|-------|--------|--------|
| `isRunning` | RAM `cameras[].enabled` | Zone có **≥1 camera** đang bật **công tắc** cho phép mở RTSP / decode |
| `isStreaming` | RAM `cameras[].streaming` | Zone có **≥1 camera** đã kết nối RTSP và **có frame** |
| `isConfigEnabled` | Mongo `zones.enabled` | Config zone có được phép dùng (không phải runtime) |
| `cameraCount` | Mongo cameras theo `zone_id` | Số camera gán zone — **không** nói đang chạy |

### RAM là gì?

Trạng thái trong process backend (`CameraManager`), **không** ghi Mongo.

- Thread camera đã tạo lúc runtime start.
- `enabled = false` → thread idle, **không** decode RTSP (dù URL còn trong DB).
- `enabled = true` → được phép mở decoder; `streaming = true` chỉ khi RTSP OK + có frame.

---

## Khi nào dùng field nào (FE)

| UI cần | Dùng |
|--------|------|
| Badge “fleet đang live / có hình” | `zones.some(z => z.isStreaming)` |
| Badge “hệ thống đã bật công tắc” (sau start, có thể RTSP fail) | `zones.some(z => z.isRunning)` |
| Zone bị tắt trong config | `isConfigEnabled === false` |

**Khuyến nghị badge “live”:** dùng `isStreaming`, **không** dùng `isRunning`.

### Ví dụ TypeScript

```ts
// Fleet live (có ít nhất 1 zone đang có frame)
const fleetLive = zones.some((z) => z.isStreaming);

// Zone vừa start nhưng RTSP chưa lên / die
const zoneArmedButOffline = (z) => z.isRunning && !z.isStreaming;
```

### Sau `POST /api/v1/system/start_all`

| Kết quả HTTP | `isRunning` | `isStreaming` (điển hình) |
|--------------|-------------|---------------------------|
| `200` (≥1 cam streaming) | `true` | `true` (ít nhất zone có cam stream) |
| `503` — model / runtime chưa sẵn | thường `false` | `false` |
| `503` — “No camera streaming…” | **`true`** (đã bật enabled, không rollback) | **`false`** |

`start_all` 503 vì RTSP **không** đồng nghĩa “không còn cam enabled”. Hydrate badge từ `isRunning` sẽ báo “đang chạy” dù chưa có frame — đó là đúng contract cũ, không phải lệch state.

---

## Nguồn đối chiếu chi tiết hơn

- Per-camera: `GET /api/v1/cameras/...` hoặc poll `cameras.items[].status`  
  (`disabled` | `offline` | `streaming`)
- Zone-level gọn: `isRunning` / `isStreaming` trên `get_zones` / poll

Không dùng `GET /api/v1/runtime/get_status` cho badge live — response hiện chỉ aggregate `total/enabled/alive`, **không** expose `streaming`.

---

## Checklist tích hợp FE

1. Thêm type `isStreaming: boolean` vào zone model.
2. Đổi hydrate badge fleet / zone live → `isStreaming`.
3. (Tuỳ UX) giữ `isRunning` cho trạng thái “armed / đã start”.
4. Poll: đọc `zones.items[].isStreaming` (BE đã forward).
5. Sau `start_all` fail: dựa `isStreaming` (hoặc message 503), không suy ra từ `isRunning === false`.
