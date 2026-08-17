# Phase 0 — Skeleton & quy ước

**Status:** Done (cùng đợt Phase 1)

## Mục tiêu

Tạo khung thư mục đích và quy ước import trước khi chuyển logic.

## Checklist

- [x] Tạo `application/`
- [x] Tạo `infrastructure/persistence|vision|ics|storage/`
- [x] Tạo `docs/clean-architecture/` overview + phase docs
- [x] Quy ước: `domain` không import framework I/O nặng
- [x] Smoke checklist tay vẫn giữ (xem Phase 1 — verification)

## Không làm ở phase này

- Không move logic `core/` / `service/`
- Không đổi API HTTP

## Exit criteria

- Folder đích tồn tại
- App chạy như cũ (không đổi behavior)
