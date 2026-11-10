# Contract FE — Sandbox (smoke test dispatch theo priority)

> Cập nhật: 2026-10-07  
> Liên quan: [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md), [fe-api-active-tasks.md](./fe-api-active-tasks.md), [fe-api-unlock-by-order-status.md](./fe-api-unlock-by-order-status.md)

**Sandbox** = BE thay camera / AI / ICS bằng bản giả. Node vẫn thuộc ROI camera trong Mongo;
FE bật/tắt "có hàng" tại từng node thay cho video, và đóng vai ICS báo trạng thái lệnh.

Chỉ tồn tại khi BE chạy `RUNTIME_MODE=sandbox` (DB bắt buộc đuôi `_sandbox`).
Production → mọi route dưới đây trả `404` (router không mount).

Auth: Bearer, quyền `system.control`.

---

## Trình tự chạy

Luồng scan / dispatch chi tiết: [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md).

1. `POST /api/v1/system/start-cameras` — bật camera + inference → tick bắt đầu đẩy `detected` vào runtime. **Chưa gửi ICS.**
2. Bật start (`detected: true`), để end trống (`detected: false`). Chờ start `isReady` (SSE / `get_pending_pairs`).
3. `POST /api/v1/runtime/dispatch` — chụp batch theo col (head → tail), mở cổng gửi.
4. BE gửi **1 lệnh / zone**, theo col rồi priority (luật đầy đủ: [fe-api-dispatch-batch.md](./fe-api-dispatch-batch.md)) → SSE `dispatch.task`.
5. Mô phỏng xe lấy hàng: start vừa chạy → `detected: false` (**FE/operator làm tay; BE không chặn**).
6. ICS giả báo `6` rồi `3` → zone hết lệnh → lệnh kế trong **cùng zone**. Zone kia chạy song song.
7. Gửi hết batch → cổng đóng (`batch_complete`). Batch kẹt → `cancel-batch`.

**Inference & cổng gửi:**

| Thời điểm | Inference | Cổng gửi ICS |
|-----------|-----------|--------------|
| Runtime vừa start | **pause** | đóng |
| Sau `start-cameras` | chạy | đóng |
| Sau `dispatch` | chạy | **mở** |
| Gửi hết / `cancel-batch` | chạy | đóng |
| Sau `pause-scan` / `stop_all` | pause | đóng |

Start ready mới **ngoài batch** không đóng cổng — chờ `dispatch` lần sau.
`set_node_state` khi inference pause: desired được lưu nhưng **chưa** vào runtime cho tới `start-cameras`.

---

## `GET /api/v1/sandbox/get_nodes`

Bảng **desired** state (FE đã đặt). Không phải SSOT metadata node.

```json
{
  "items": [
    {
      "nodeId": "start_9000001",
      "cameraId": 1,
      "cameraEnabled": true,
      "detected": false
    }
  ]
}
```

| Field | Ý nghĩa |
|-------|---------|
| `nodeId` | Node thuộc ROI camera |
| `cameraId` | Camera chứa ROI |
| `cameraEnabled` | Camera đang bật trong runtime |
| `detected` | State mong muốn FE đã đặt (**không** phải `isReady`) |

**Không có `zoneId` / `kind` / `priority`.** FE join warehouse `GET /api/v1/nodes/get_nodes` (hoặc nguồn node sẵn có) để lấy metadata và nhóm theo zone.

Trạng thái runtime thật (`detected` / `isReady` / `lock`) lấy từ SSE `GET /api/v1/runtime/events`.

| HTTP | Khi nào |
|------|---------|
| `200` | Runtime sandbox đang chạy — `items` có thể rỗng nếu chưa có ROI |
| `503` | Runtime sandbox chưa chạy (giống `set_node_state`) |
| `404` | Không phải sandbox mode (route không tồn tại) |

---

## `POST /api/v1/sandbox/set_node_state`

```json
{ "nodeId": "start_9000001", "detected": true }
```

| Node | `detected: true` | `detected: false` |
|------|------------------|-------------------|
| start | Có hàng → ready sau `START_READY_AFTER_SEC` | Trống |
| end | Có hàng (bận) | Trống → ready sau `END_READY_AFTER_SEC` |

| HTTP | Khi nào |
|------|---------|
| `200` | `{ "nodeId", "detected" }` |
| `404` | Node không thuộc ROI camera nào |
| `503` | Runtime sandbox chưa chạy |

---

## `GET /api/v1/sandbox/get_orders`

Lệnh ICS giả đã nhận, `seq` = thứ tự gửi (đối chiếu priority).

```json
{
  "items": [
    {
      "seq": 1,
      "orderId": "S-9000001-9000101-2026-10-06 17:00:00.123456",
      "taskPath": ["9000001,9000101"],
      "status": 9,
      "sentAt": 1791280800.12
    }
  ]
}
```

| HTTP | Khi nào |
|------|---------|
| `200` | `{ "items": [...] }` |
| `503` | Runtime sandbox chưa chạy |
| `404` | Không phải sandbox mode |

---

## `POST /api/v1/sandbox/set_order_status`

Cùng luồng webhook thật `unlock_by_order_status` (panel + lock + `dispatch_logs`).

```json
{ "orderId": "S-9000001-9000101-2026-10-06 17:00:00.123456", "status": 3 }
```

| `status` | Hiệu ứng |
|----------|----------|
| `6` | Panel → `inprogress` |
| `3` / `23` | Gỡ lock start + end, xóa khỏi panel |

| HTTP | Khi nào |
|------|---------|
| `200` | Xử lý OK |
| `404` | `orderId` không có trong ICS giả |
| `503` | Runtime sandbox chưa chạy |

**Không enforce** “start phải `detected: false` trước khi báo `3`”. BE không trả `400` nếu start còn hàng. Quên tắt → start ready lại sau unlock → lệnh kế tiếp sai thứ tự priority. Đây là checklist operator/FE, không phải validation API.

---

## Đề xuất màn Sandbox (FE)

- Lưới node nhóm theo zone (metadata từ warehouse nodes + toggle từ sandbox `get_nodes`)
- Badge `isReady` / lock từ SSE `node.runtime`
- Bảng `get_orders` theo `seq` + nút `6` / `3` mỗi dòng
- Nút `start-cameras` → `dispatch` / `cancel-batch`, xem `waitingFor` / `stuckNodes` / `filledNodes`
- Ẩn toàn bộ màn khi `GET /api/v1/sandbox/get_nodes` trả `404` (không phải sandbox)

---

## Dữ liệu seed (`scripts/seed_sandbox.py`)

2 zone `SBA`, `SBB` × 10 start (P1–P10), **1 end mỗi zone** (`end_9000101`, `end_9000102`).
Pair chỉ trong zone — không xuyên zone.
Thứ tự mong đợi: **theo từng zone** P1 → P2 → … (hai zone song song, không đối chiếu xen kẽ).

Sau khi pull code mới: chạy lại `uv run python scripts/seed_sandbox.py`.

---

## Smoke trail log (tạm — đối chiếu checklist)

BE ghi file `logs/sandbox/smoke_trail_YYYYMMDD.log` (JSON mỗi dòng) khi `RUNTIME_MODE=sandbox`.

| `source` | `action` | Ý nghĩa |
|----------|----------|---------|
| `api` | `start_cameras` | Operator bật camera + inference (chưa gửi ICS) |
| `api` | `start_all` / `start_scan` | Alias cũ (deprecated) |
| `api` | `confirm_dispatch` | Chụp batch (`batchSize` / `batchNodes` theo priority), mở cổng |
| `api` | `cancel_batch` | Huỷ batch (inference vẫn chạy) |
| `api` | `pause_scan` | Operator pause + huỷ batch |
| `api` | `set_node_state` | Đổi desired detected (+ `inferencePaused`, snapshot node) |
| `api` | `set_order_status` | ICS giả báo `6` / `3` / `23` |
| `system` | `dispatch` | Hệ thống gửi lệnh (`seq`, start/end, state runtime) |
| `system` | `batch_complete` | Gửi hết batch → đóng cổng (inference vẫn chạy) |

Mỗi dòng có thể có `hint` — gợi ý bước tiếp theo / lỗi checklist thường gặp.
Production: không ghi (no-op).

---

## Checklist

- [ ] `start-cameras` → set detected → chờ `isReady` → `dispatch`
- [ ] Bật **hết** start của đợt trước khi `dispatch` (bật thêm sau đó → nằm ngoài batch, chờ đợt sau)
- [ ] Bật start_1 và start_5 cùng col, chờ ready, `dispatch` → batch gồm 1..5 (2..4 là `filledNodes`)
- [ ] Sau mỗi lệnh: tắt `detected` của start **trước** khi báo `3` (FE/operator; BE không chặn)
- [ ] Thấy `batch_complete` → `dispatch` lại
- [ ] Đối chiếu `seq` **theo từng zone** (SBA: P1→P2…; SBB: P1→P2…)
- [ ] Batch kẹt → `cancel-batch` (không cần `pause-scan`)
- [ ] Join warehouse nodes để lấy `zoneId` / `kind` / priority
- [ ] Ẩn màn khi `404`; coi `503` = runtime chưa sẵn (không phải “không có sandbox”)
