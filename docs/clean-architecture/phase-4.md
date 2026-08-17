# Phase 4 — Dispatch / ICS

**Status:** Done

## Mục tiêu

Tách HTTP ICS khỏi rule dispatch. Retry trong gateway. Payload ICS **một builder** cho production + use case.

Quyết định đã chốt:

1. Giữ loop `PairManager`; strategy gọi `DispatchGateway`.
2. HTTP client: **`requests`**.
3. Retry trong **`HttpDispatchGateway`**.
4. Refactor **cả 3** strategy (Single / Empty / Double).
5. Builder chung `application/dispatch/ics_payload.py`; `RunDispatchCycle` dùng cùng format.
6. Wire gateway vào `container` lúc `runtime.start()`.
7. Unit test fake gateway + mock `requests` (không ICS server).

## Checklist thay đổi (đã làm)

- [x] `infrastructure/ics/http_dispatch_gateway.py` — POST + retry + `code == 1000`
- [x] `application/dispatch/ics_payload.py` — `build_single|empty|double_payload`
- [x] `utils/data.py` re-export deprecated
- [x] `SingleDispatch` / `EmptyDispatch` / `DoubleDispatch` inject `DispatchGateway`
- [x] `core/pair_manager.py` **không** `import requests`
- [x] `RunDispatchCycle` gửi payload ICS thật (không còn `{start, end, uuid}`)
- [x] `container.bind_dispatch_gateway` + `RuntimeService` tạo `HttpDispatchGateway`
- [x] Test payload + gateway mock + cycle dùng format ICS
- [x] `domain` + `application` không `import requests`

## Không làm ở Phase 4

- Chưa thay thread `PairManager._run` bằng `RunDispatchCycle` (giữ 1A)
- Chưa move YOLO/RTSP (Phase 5)
- Empty/Double **chưa** inject runtime (vẫn `SingleDispatch`)

## Exit criteria

- [x] `domain` + `application` không import `requests`
- [x] Dispatch test được không cần ICS server thật

---

## Luồng giả định để bạn verify

### Tình huống A — Single dispatch production

1. Node start/end ready → `PairManager.make_pairs` → `build_dispatch_pairs`.
2. `SingleDispatch` gọi `build_single_payload` → `modelProcessCode=SingleGroupAE5`, `orderId` prefix `S-`.
3. `HttpDispatchGateway.send` POST `ICS_URL`, retry 3 lần nếu fail.
4. Success (`code==1000`) → `set_pair_used` + `OnDispatchSuccess`.
5. Fail hết retry → không set flag.

**Expect unit:** `test_ics_payload.py`, `test_http_dispatch_gateway.py`  
**Manual:** 1 cặp ready + ICS mock/thật — log `[SINGLE]`.

### Tình huống B — Retry trong gateway

1. Lần 1–2: HTTP 500 hoặc exception.
2. Lần 3: 200 + `code=1000` → `send()` True; `requests.post` = 3 lần.
3. Cả 2 lần timeout → False.

**Expect unit:** `test_send_retries_then_success`, `test_send_all_retries_fail`  
Không cần ICS server.

### Tình huống C — `RunDispatchCycle` cùng payload ICS

1. Fake store: start/end ready.
2. Fake gateway OK → nhận payload `SingleGroupAE5` + `taskPath` số từ node_id (không còn `{start,end,uuid}`).
3. Gateway fail → không `set_pair_used`.

**Expect unit:** `test_run_dispatch_cycle_success_and_fail`

### Tình huống D — Empty / Double (code path, chưa runtime)

1. `EmptyDispatch` / `DoubleDispatch` cũng `gateway.send` + builder empty/double.
2. Runtime vẫn `SingleDispatch(ics_gateway)` — Empty/Double chỉ khi đổi inject.

**Manual:** không bắt buộc trừ khi đổi strategy.

### Tình huống E — Wire lúc start

1. `RuntimeService.start` → `HttpDispatchGateway(...)` → `container.bind_dispatch_gateway`.
2. `SingleDispatch(ics_gateway)` + `PairManager`.
3. `RunDispatchCycle` trên container dùng **cùng** gateway instance.

**Manual:** start app, `GET /runtime/status` có `"strategy": "SingleDispatch"`.

---

## Map file

| Vai trò | File |
|---------|------|
| Payload ICS | `application/dispatch/ics_payload.py` |
| HTTP + retry | `infrastructure/ics/http_dispatch_gateway.py` |
| Strategy | `core/pair_manager.py` (không requests) |
| Use case | `application/dispatch/run_cycle.py` |
| Re-export cũ | `utils/data.py` |

---

## Chạy test Phase 4

```bash
python -m pytest tests/application tests/domain tests/infrastructure -q
```
