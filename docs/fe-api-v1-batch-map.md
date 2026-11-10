# API `/api/v1` — Map zip (global versions)

> Cập nhật: 2026-09-11  
> Phạm vi: import / list / set active / get compress / download zip.  
> **Không** nền PGM. **Không** sync `position` / `mapPosition` từ compress. **Không** map id compress ↔ node Kortek.

Auth + quyền: Bearer.  
- `map.write` — **chỉ admin** (import, set_active)  
- `map.read` — admin / operator / viewer (list, get_compress, download)

> User đã seed trước khi thêm quyền: chạy lại `uv run python scripts/seed_users.py`
> — script **đồng bộ permissions** cho user đã có (không đổi mật khẩu). Rồi login /
> refresh lại để token nhận `map.read` / `map.write`.

---

## 1. Quy ước

| | |
|---|---|
| Phạm vi | **Global** — một `activeVersionId` toàn hệ |
| Sau import | Version mới **luôn active** |
| Lưu trữ | Zip **nguyên bản**, không giải nén cả archive |
| Validate | Zip phải có entry path **kết thúc** `…/compress.json` (vd. `compress/compress.json`) |
| Retention | Giữ tối đa `MAP_VERSION_KEEP` (mặc định **5**); vượt → xoá bản **cũ nhất** (không xoá bản đang active) |
| Render FE | Chỉ cần `get_compress` → `{ versionId, compress }` |

Settings: `MAP_STORAGE_DIR` (mặc định `data/maps`), `MAP_VERSION_KEEP=5`, `MAP_MAX_UPLOAD_MB=100`.

---

## 2. Endpoints

### `POST /api/v1/maps/import_map`

`multipart/form-data`, field **`file`**.

**200**

```json
{
  "versionId": "…",
  "isActive": true,
  "pruned": ["oldVersionId…"],
  "byteSize": 123456,
  "checksum": "sha256…"
}
```

| Status | |
|---|---|
| 400 | Không phải zip / thiếu `…/compress.json` / JSON lỗi / quá dung lượng |
| 403 | Không phải admin (`map.write`) |

### `GET /api/v1/maps/list_map_versions`

```json
{
  "activeVersionId": "…",
  "items": [
    {
      "versionId": "…",
      "originalFilename": "0805.zip",
      "byteSize": 123,
      "checksum": "…",
      "createdAt": "…",
      "createdBy": "admin",
      "isActive": true
    }
  ]
}
```

### `POST /api/v1/maps/set_active_map`

Restore bản cũ:

```json
{ "versionId": "…" }
```

**200:** `{ "versionId": "…", "isActive": true }`

### `GET /api/v1/maps/get_compress?versionId=` (optional)

Mặc định = bản active.

```json
{
  "versionId": "…",
  "compress": {
    "nodeKeys": ["x", "y", "type", "content", "name", "…"],
    "nodeArr": [ … ],
    "lineKeys": [ … ],
    "lineArr": [ … ],
    "width": 230000,
    "height": 100000,
    "xAttrMin": 10000,
    "yAttrMin": 10000
  }
}
```

FE parse columnar (`nodeKeys` + `nodeArr`) để vẽ. Không dùng id compress để ghép Mongo.

### `GET /api/v1/maps/download_map_zip?versionId=` (optional)

Binary `application/zip` + `Content-Disposition: attachment`. Mặc định bản active.

---

## 3. Checklist FE

- [ ] Upload zip (`FormData` + field `file`) chỉ hiện với `map.write`  
- [ ] Sau import: gọi `get_compress` (hoặc dùng `versionId` trả về)  
- [ ] UI danh sách version + nút restore (`set_active_map`)  
- [ ] Nút tải lại zip gốc  
- [ ] User admin cũ: seed lại permissions nếu thiếu `map.read` / `map.write`  

---

## 4. Ngoài phạm vi

- Nền PGM / convert PNG  
- Sync `position` / `mapPosition` từ compress  
- Map theo zone  
