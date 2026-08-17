# Phase 3 — Infrastructure persistence

**Status:** Done

## Mục tiêu

Mongo / repository nằm dưới `infrastructure/persistence`, implement Port. Không còn god folder `repository/` ở root, không còn pymongo trong `core/`.

Quyết định đã chốt:

1. Move hết, **xóa** `repository/` (không shim).
2. **Xóa** `core/camera_config_repository.py` (dead code).
3. Mongo class implement đủ method Port → bỏ adapter repo mỏng.
4. Move cả snapshot / logs / zone (kể cả chưa wire HTTP).
5. Không thêm Mongo unit test — chạy lại pytest fake hiện có.

## Checklist thay đổi (đã làm)

- [x] Move `repository/*` → `infrastructure/persistence/`
- [x] Xóa `core/camera_config_repository.py`
- [x] `CameraRepository` / `PairsRepository` / `NodeRepository` implement Port (`get_by_area`, `update_by_camera_id`, `get_by_zone`, `delete_by_node_id`, …)
- [x] `container.bind_repos` nhận repo concrete, không bọc `CameraConfigAdapter` / `PairsRepoAdapter` / `NodeRepoAdapter`
- [x] `app.py` / `runtime_service` import `infrastructure.persistence.*`
- [x] Xóa folder `repository/`
- [x] Use case test vẫn fake — **34 passed**

## Không làm ở Phase 3

- Chưa HTTP ICS (Phase 4)
- Chưa move YOLO/RTSP (Phase 5)
- Chưa Mongo integration test

## Exit criteria

- [x] Không còn pymongo trong `core/`
- [x] Root không còn folder `repository/`

---

## Luồng giả định để bạn verify

### Tình huống A — Startup vẫn load camera + pairs từ Mongo

1. `app.py` lifespan: `connect(MONGODB_URL, MONGODB_DB)` từ `infrastructure.persistence.db`.
2. `container.bind_repos(camera_repository, pairs_repository, node_repository, VALIDATE_PAIRS_BY_ZONE)`.
3. `runtime_service.start()` gọi `camera_repository.get_all()` và `pairs_repository.get_as_tuples()`.

**Expect:** App start như cũ nếu Mongo có data. Import `from repository...` phải fail (folder đã xóa).

**Manual:** `python main.py` / uvicorn — log `MongoDB connected`, `Loaded N cameras, M pairs`.

### Tình huống B — CRUD HTTP đi thẳng vào Port implementation

1. `GET /cameras/config` → `ListCameraConfigs` → `CameraRepository.get_all()`.
2. `GET /cameras/config/area/AE5` → `get_by_area("AE5")` (query `zone_id`, không filter `enabled` — khác `get_by_zone` dùng lúc runtime).
3. `PUT /cameras/config/{id}` → `update_by_camera_id`.
4. `GET /pairs/zone/AE5` → `PairsRepository.get_by_zone`.
5. `DELETE /nodes/{id}` → `delete_by_node_id`.

**Expect unit:** `tests/application/test_crud.py` (fake repo, không Mongo).  
**Manual:** CRUD một camera/pair/node trên API thật.

### Tình huống C — Dead code đã biến

1. Không còn `core/camera_config_repository.py` (pymongo sync `load_cameras_from_mongodb`).
2. Runtime **không** đọc collection `node_id` qua file đó; chỉ `cameras` collection qua `CameraRepository`.

**Expect:** `rg pymongo core` = không match.

### Tình huống D — Repo chưa wire HTTP vẫn nằm đúng chỗ

`snapshot_repository`, `dispatch_log_repository`, `zone_repository`, `log_repositories` đã move. Chưa có route — Phase sau có thể bind khi cần. Không để lại ở root.

### Tình huống E — Unbound vs bound repos

1. Trước `bind_repos`: Null Port → CRUD fail/empty (không crash import).
2. Sau lifespan: concrete Mongo repo.

**Expect:** pytest không đụng Mongo; container test use case vẫn dùng Fake*Repo.

---

## Map file

| Cũ | Mới |
|----|-----|
| `repository/db.py` | `infrastructure/persistence/db.py` |
| `repository/base_repository.py` | `infrastructure/persistence/base_repository.py` |
| `repository/camera_repository.py` | `infrastructure/persistence/camera_repository.py` |
| `repository/pairs_repository.py` | `infrastructure/persistence/pairs_repository.py` |
| `repository/node_repository.py` | `infrastructure/persistence/node_repository.py` |
| `repository/snapshot_repository.py` | `infrastructure/persistence/snapshot_repository.py` |
| `repository/dispatch_log_repository.py` | `infrastructure/persistence/dispatch_log_repository.py` |
| `repository/zone_repository.py` | `infrastructure/persistence/zone_repository.py` |
| `repository/log_repositories.py` | `infrastructure/persistence/log_repositories.py` |
| `core/camera_config_repository.py` | **xóa** |

---

## Chạy test Phase 3

```bash
python -m pytest tests/application tests/domain -q
```
