# WebRTC live preview — contract FE (`/api/v1`)

> Cập nhật: **2026-09-29**  
> Phạm vi: xem live camera qua **WHEP** (WebRTC over HTTP).  
> Breaking change: path cũ `/cameras/...` (không auth) đã **gỡ**. Tất cả endpoint dưới đây nằm dưới **`/api/v1/cameras`** và **bắt buộc Bearer**.  
> Health MediaMTX: `GET /api/v1/system/get_health` → `webrtc.alive`.

---

## 1. Quy ước chung

| | Giá trị |
|---|---|
| Prefix | **`/api/v1/cameras/...`** |
| Auth | **`Authorization: Bearer <accessToken>`** |
| Permission | **`camera.read`** |
| Protocol | **WHEP**: POST SDP offer → SDP answer |
| Giới hạn | Tối đa **4** session đồng thời (grid 2×2) trên toàn hệ thống |
| Lỗi JSON | HTTP status thật + `{"message": "..."}` — **không** còn `{ "success": false, "error": "..." }` |
| Base URL | Cùng origin / proxy với API backend |

**Thuật ngữ ngắn**

| Từ | Nghĩa |
|---|---|
| **WHEP** | WebRTC-HTTP Egress Protocol — bắt tay SDP qua HTTP, media đi UDP/SRTP |
| **SDP** | Session Description Protocol — text mô tả codec/ICE; body raw, **không** JSON |
| **ICE** | STUN/TURN giúp peer tìm đường mạng; LAN thường `iceServers: []` |
| **recvonly** | FE chỉ **nhận** video, không gửi camera máy client |

> FE **không** gọi trực tiếp MediaMTX. Signaling luôn qua FastAPI.

---

## 2. Bảng migrate path (cũ → mới)

| Mục đích | Path cũ (đã xóa) | Path mới |
|---|---|---|
| ICE | `GET /cameras/webrtc/ice` | `GET /api/v1/cameras/webrtc/ice` |
| Slot grid | `GET /cameras/webrtc/status` | `GET /api/v1/cameras/webrtc/status` |
| Connect preview | `POST /cameras/{id}/webrtc/preview/whep` | `POST /api/v1/cameras/{id}/webrtc/preview/whep` |
| Connect detect | `POST /cameras/{id}/webrtc/detect/whep` | `POST /api/v1/cameras/{id}/webrtc/detect/whep` |
| Hangup | `DELETE /cameras/{id}/webrtc/sessions/{sid}` | `DELETE /api/v1/cameras/{id}/webrtc/sessions/{sid}` |
| Overlay meta | `GET /cameras/{id}/preview/meta` | `GET /api/v1/cameras/{id}/preview/meta` |
| JPEG detect overlay | `GET /cameras/{id}/preview/detect` | **Đã xóa** — dùng WHEP detect + meta |
| Health (ops) | `GET /health` | `GET /api/v1/system/get_health` (đã có sẵn) |

`{id}` / `cameraId` = số nguyên Mongo `cameraId` (vd. `20`).

---

## 3. Checklist endpoint

| Mục đích | Method + path | Auth |
|---|---|---|
| ICE servers | `GET /api/v1/cameras/webrtc/ice` | Bearer + `camera.read` |
| Số slot đang dùng | `GET /api/v1/cameras/webrtc/status` | Bearer + `camera.read` |
| Connect preview | `POST /api/v1/cameras/{cameraId}/webrtc/preview/whep` | Bearer + `camera.read` |
| Connect detect | `POST /api/v1/cameras/{cameraId}/webrtc/detect/whep` | Bearer + `camera.read` |
| Hangup | `DELETE /api/v1/cameras/{cameraId}/webrtc/sessions/{sessionId}` | Bearer + `camera.read` |
| Overlay (chỉ detect) | `GET /api/v1/cameras/{cameraId}/preview/meta` | Bearer + `camera.read` |
| MediaMTX sống? | `GET /api/v1/system/get_health` → `webrtc.alive` | Bearer (login) |

---

## 4. ICE

### `GET /api/v1/cameras/webrtc/ice`

**200**

```json
{
  "iceServers": []
}
```

- `[]` = LAN (không STUN/TURN) — bình thường.
- Có STUN/TURN khi server cấu hình `WEBRTC_STUN_URL` / `WEBRTC_TURN_*`.

**FE:** gọi 1 lần khi vào màn live → `new RTCPeerConnection({ iceServers })`.

| HTTP | Ý nghĩa |
|---|---|
| **401** | Thiếu / sai token |
| **403** | Thiếu `camera.read` |

---

## 5. Capacity (grid)

### `GET /api/v1/cameras/webrtc/status`

**200** (data trần)

```json
{
  "count": 2,
  "max": 4
}
```

**FE:** trước Connect, nếu `count >= max` → chặn UI (tránh 409). Poll ~2s khi đang mở màn live.

---

## 6. Connect — WHEP

### `POST /api/v1/cameras/{cameraId}/webrtc/preview/whep`

Video passthrough RTSP → WebRTC (không vẽ ROI trên stream).

### `POST /api/v1/cameras/{cameraId}/webrtc/detect/whep`

Cùng video track như preview. Overlay ROI/bbox = poll `GET .../preview/meta` + canvas (không DataChannel).

### Request

| | |
|---|---|
| Headers | `Authorization: Bearer …` · `Content-Type: application/sdp` · `Accept: application/sdp` |
| Body | **Chuỗi SDP offer** (`pc.localDescription.sdp`) — raw text, **không** JSON |

```http
POST /api/v1/cameras/20/webrtc/preview/whep HTTP/1.1
Authorization: Bearer <accessToken>
Content-Type: application/sdp
Accept: application/sdp

v=0
o=- 0 0 IN IP4 127.0.0.1
...
```

### Response thành công

| | |
|---|---|
| Status | **201** |
| `Content-Type` | `application/sdp` |
| Body | SDP answer (text) |
| Header | `Location: /api/v1/cameras/{cameraId}/webrtc/sessions/{sessionId}` |

**FE sau 201:**

1. `await pc.setRemoteDescription({ type: "answer", sdp: bodyText })`
2. Gắn `pc.ontrack` → `video.srcObject`
3. Lưu `sessionId` từ `Location` (segment cuối URL)

### Response lỗi

```json
{
  "message": "WebRTC not ready"
}
```

| HTTP | Khi nào | FE làm gì |
|---|---|---|
| **400** | Thiếu SDP / mode sai | Báo lỗi |
| **401** / **403** | Auth | Login / thiếu quyền |
| **404** | Camera / RTSP không có | Báo lỗi |
| **409** | Đã đủ 4 session | Hangup ô khác rồi Connect lại |
| **503** | MediaMTX chưa sẵn / WHEP fail | Báo lỗi; nếu vừa tạo slot thất bại, thử lại sau |

> **Lưu ý breaking:** body lỗi **không** còn field `success` / `error` / `session_id`. Chỉ `message`.

---

## 7. Flow Connect (thứ tự bắt buộc)

```
1. GET /api/v1/cameras/webrtc/ice          (+ Bearer)
2. GET /api/v1/cameras/webrtc/status       (count < max)
3. pc = new RTCPeerConnection({ iceServers })
4. pc.addTransceiver("video", { direction: "recvonly" })
5. pc.ontrack = … → video.srcObject
6. offer = await pc.createOffer()
7. await pc.setLocalDescription(offer)
8. Đợi ICE gathering xong (iceGatheringState === "complete" hoặc timeout ngắn)
9. POST .../webrtc/preview/whep  body = pc.localDescription.sdp
10. 201 → setRemoteDescription(answer) + lưu sessionId từ Location
11. (detect) bắt đầu poll GET .../preview/meta
```

---

## 8. Hangup

### `DELETE /api/v1/cameras/{cameraId}/webrtc/sessions/{sessionId}`

**200**

```json
{
  "session_id": "…",
  "camera_id": 20
}
```

| Status | Ý nghĩa |
|---|---|
| **200** | Đã đóng + giải phóng slot |
| **404** | Session không tồn tại / sai camera |
| **401** / **403** | Auth |

**FE:** luôn gọi khi Hangup, unmount, đổi camera — rồi `pc.close()` và dừng poll meta.

---

## 9. Detect overlay — meta poll

### `GET /api/v1/cameras/{cameraId}/preview/meta`

Chỉ cần khi mode **detect**. Gợi ý interval **~200 ms**.

**200** — tọa độ trong không gian infer `w`×`h` (thường 640×480):

```json
{
  "w": 640,
  "h": 480,
  "ts": 1726123456.789,
  "rois": [
    { "node_id": "start_1", "roi": [x, y, w, h] }
  ],
  "dets": [
    { "cls": 0, "conf": 0.92, "xyxy": [x1, y1, x2, y2] }
  ]
}
```

| Field | Ý nghĩa |
|---|---|
| `rois[].roi` | `[x, y, w, h]` pixel |
| `dets[].cls` | class id (số nguyên) |
| `dets[].xyxy` | `[x1, y1, x2, y2]` |
| `ts` | timestamp meta |

**FE:** scale ROI/bbox theo kích thước `<video>` / canvas.

| HTTP | Khi nào |
|---|---|
| **404** | Camera không tồn tại |
| **409** | Camera chưa streaming |
| **503** | Runtime / meta chưa sẵn |

---

## 10. Health MediaMTX (không thay signaling)

`GET /api/v1/system/get_health` (Bearer) → `webrtc.alive`.

- `alive: false` → Connect WHEP dễ **503**; hiện banner, vẫn cho phép thử lại.
- **Không** dùng health thay cho `webrtc/status` (số slot).

---

## 11. Pseudo-code tối thiểu (preview)

```ts
const headers = { Authorization: `Bearer ${accessToken}` };

const { iceServers } = await api.get("/api/v1/cameras/webrtc/ice", { headers });
const { count, max } = await api.get("/api/v1/cameras/webrtc/status", { headers });
if (count >= max) throw new Error("Max 4 WebRTC sessions");

const pc = new RTCPeerConnection({ iceServers });
pc.addTransceiver("video", { direction: "recvonly" });
pc.ontrack = (ev) => {
  videoEl.srcObject = ev.streams[0] ?? new MediaStream([ev.track]);
};

await pc.setLocalDescription(await pc.createOffer());
// wait ICE complete…

const res = await fetch(`/api/v1/cameras/${cameraId}/webrtc/preview/whep`, {
  method: "POST",
  headers: {
    ...headers,
    "Content-Type": "application/sdp",
    Accept: "application/sdp",
  },
  body: pc.localDescription!.sdp,
});

if (res.status === 201) {
  const sdp = await res.text();
  const sessionId = (res.headers.get("Location") || "")
    .split("/")
    .filter(Boolean)
    .pop()!;
  await pc.setRemoteDescription({ type: "answer", sdp });
  return { pc, sessionId };
}

const err = await res.json().catch(() => ({}));
throw new Error(err.message || `WHEP ${res.status}`);
```

Hangup:

```ts
await fetch(`/api/v1/cameras/${cameraId}/webrtc/sessions/${sessionId}`, {
  method: "DELETE",
  headers: { Authorization: `Bearer ${accessToken}` },
});
pc.close();
```

---

## 12. Lưu ý tích hợp FE

1. Proxy/CORS: forward cả prefix **`/api/v1/cameras/**`** (không còn `/cameras/**` ngoài v1).
2. Mọi request WebRTC phải gắn Bearer — kể cả poll `preview/meta`.
3. **Không** hardcode MediaMTX `:8890` trên FE.
4. Đóng tab / route change → Hangup đủ session đang giữ (tránh chiếm 4 slot).
5. Mix được: 2 preview + 2 detect trong cùng 4 slot.
6. JPEG thumbnail (nếu cần) dùng `GET /api/v1/cameras/get_snapshot` — **không** thay WebRTC.
7. Parse lỗi theo **`message`** + HTTP status (chuẩn `/api/v1`).

---

## 13. Demo nhanh local

1. Login: `POST /api/v1/auth/login` → lấy `accessToken`
2. `uv run uvicorn app:app --host 0.0.0.0 --port 5000`
3. Test bằng FE thật (trang demo `static/webrtc.html` đã gỡ khỏi repo)
