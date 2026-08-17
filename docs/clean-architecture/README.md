# Clean Architecture Migration — Overview

Mục tiêu refactor:

1. Unit test dễ dàng, không phụ thuộc RTSP / YOLO / Mongo.
2. Tránh god file / god folder.

## Target structure

```text
domain/              # rule nghiệp vụ thuần
application/         # use cases + ports
infrastructure/      # persistence, vision, ics, storage
presentation/        # FastAPI routes
config/              # env / pydantic settings
utils/               # helper cross-cutting
```

`service/` và `core/` đã xóa (Phase 6–7). `repository/` đã chuyển sang `infrastructure/persistence/` (Phase 3).

## Nguyên tắc

- `domain` không import FastAPI / motor / torch / requests.
- `application` chỉ phụ thuộc `domain` + ports (ABC/Protocol).
- Concrete Mongo / YOLO / HTTP chỉ nằm ở `infrastructure` và được wire ở composition root (`app.py` / runtime start).
- Mỗi phase: app vẫn chạy được + có checklist + (nếu có) unit test mới.

## Trạng thái phase

| Phase | Nội dung | Status |
|-------|----------|--------|
| 0 | Skeleton + quy ước | Done (cùng đợt Phase 1) |
| 1 | Domain thuần + facade + pytest | **Done** |
| 2 | Ports + use cases (phá God Service) | **Done** |
| 3 | Infrastructure persistence | **Done** |
| 4 | Dispatch / ICS gateway | **Done** |
| 5 | Vision & camera runtime | **Done** |
| 6 | Storage + dọn composition root | **Done** |
| 7 | CI / củng cố / bỏ facade thừa | **Done** |

## Docs từng phase

- [phase-0.md](./phase-0.md)
- [phase-1.md](./phase-1.md) — checklist + thay đổi đã làm + luồng giả định
- [phase-2.md](./phase-2.md) — checklist + luồng giả định
- [phase-3.md](./phase-3.md) — checklist + luồng giả định
- [phase-4.md](./phase-4.md) — checklist + luồng giả định
- [phase-5.md](./phase-5.md)
- [phase-6.md](./phase-6.md)
- [phase-7.md](./phase-7.md)

## Dict `points` (Phase 1 → 7)

`points` vẫn là `dict` **nội bộ** `NodeState` (không method-only). Facade `core/state_manager.py` đã xóa ở Phase 7. Use case đi qua `NodeStateStore`.

## Chạy unit test

```bash
pip install -e ".[dev]"
# hoặc: pip install pytest
pytest
```

Không cần RTSP, model, Mongo cho các test `tests/domain/` và `tests/application/`.
