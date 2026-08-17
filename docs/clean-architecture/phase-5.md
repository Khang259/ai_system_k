# Phase 5 — Vision & camera runtime

**Status:** Done

## Mục tiêu

Chuyển AI/video ra `infrastructure/vision`, hết god folder `core/` phía vision.

Quyết định đã chốt:

1. **Move + xóa** — chuyển sang `infrastructure/vision/`, xóa bản `core/`
2. **Snapshot** — `snapshot_manager` giữ ở `core/` đến Phase 6
3. **State** — `CameraProcessor` vẫn gọi `state_manager.get_state_nodes()` (không refactor Port detection)
4. **Port** — không thêm Port mới; adapter Phase 2 đủ
5. **Import** — `RuntimeService` import trực tiếp `infrastructure.vision.*`
6. **Test** — pytest hiện có + smoke import test
7. **Docs** — cập nhật phase-5 + README

## Checklist thay đổi (đã làm)

- [x] Move `inference_engine`, `gpu_video_decoder`, `detection` → `infrastructure/vision/`
- [x] Move `camera_processor`, `camera_manager` → `infrastructure/vision/`
- [x] Sửa import nội bộ (`camera_processor` → `infrastructure.vision.*`, `state_manager` vẫn từ `core/`)
- [x] `service/runtime_service.py` import từ `infrastructure.vision`
- [x] Xóa 5 file vision cũ trong `core/`
- [x] `infrastructure/vision/__init__.py` re-export `CameraManager`, `InferenceEngine`
- [x] `tests/infrastructure/test_vision_imports.py` — smoke import không cần GPU
- [x] Import `config.settings` thay `from config import settings` (gpu_decoder, detection)

## Không làm ở Phase 5

- Chưa move `snapshot_manager` (Phase 6)
- Chưa refactor worker báo detection qua Port riêng
- Không thêm `InferencePort` / Port detection mới
- Không unit test YOLO/RTSP thật

## Exit criteria

- [x] Vision nằm hết dưới `infrastructure/vision/`
- [x] `core/` còn: `pair_manager`, `state_manager`, `snapshot_manager`
- [x] Domain/application vẫn test không GPU

## Luồng giả định verify

1. **Startup runtime**
   - `RuntimeService.start()` tạo `InferenceEngine` + `CameraManager` từ `infrastructure.vision`
   - `container.bind_runtime(cam_mgr, inference_eng, sm, self)` — adapter Phase 2 không đổi logic

2. **Camera thread**
   - `CameraProcessor.run()` mở `GPUVideoDecoder` → gửi frame vào `InferenceEngine`
   - Nhận detection → `has_object_in_roi()` → `state_manager.get_state_nodes(node_id, has_obj)`
   - Snapshot (nếu bật) vẫn qua `core.snapshot_manager`

3. **Import boundary**
   - `domain/` + `application/` không import `torch` / `ultralytics`
   - Vision chỉ wire ở composition root (`RuntimeService`)

4. **Test**
   ```bash
   python -m pytest tests/application tests/domain tests/infrastructure -q
   ```
   - Smoke: `test_vision_imports` import module/class không load model

## `core/` sau Phase 5

| File | Vai trò | Phase tiếp |
|------|---------|------------|
| `pair_manager.py` | Dispatch loop + strategies | Phase 6+ |
| `state_manager.py` | Facade → NodeState | Phase 7 |
| `snapshot_manager.py` | Filesystem snapshot | **Phase 6** |
