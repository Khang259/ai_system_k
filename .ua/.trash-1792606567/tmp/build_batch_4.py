# -*- coding: utf-8 -*-
"""Generate batch-4.json GraphFragment for Understand-Anything."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(r"d:\Prj\kortek")
UA = ROOT / ".ua"
EXTRACT_PATH = UA / "tmp" / "ua-file-extract-results-4.json"
INPUT_PATH = UA / "tmp" / "ua-file-analyzer-input-4.json"
BATCHES_PATH = UA / "intermediate" / "batches.json"
OUT_DIR = UA / "intermediate"
BATCH_INDEX = 4

FILE_SUMMARIES: dict[str, tuple[str, list[str], str]] = {
    "application/container.py": (
        "Composition root (DI): lớp AppContainer gắn port/infrastructure vào use case, "
        "quản lý runtime camera/dispatch/auth và singleton module-level `container`.",
        ["factory", "singleton", "service", "dependency-injection"],
        "complex",
    ),
    "domain/permissions.py": (
        "Ánh xạ role người dùng sang tập permission string dùng cho RBAC ở tầng presentation.",
        ["validation", "security", "data-model"],
        "simple",
    ),
    "presentation/deps.py": (
        "FastAPI dependencies: trích JWT, user hiện tại, SSE token và factory `require_permission`.",
        ["middleware", "security", "api-handler"],
        "moderate",
    ),
    "presentation/http_v1.py": (
        "Helper chuyển UseCaseResult sang JSONResponse, audit log và phân trang cho router v1.",
        ["utility", "api-handler", "serialization"],
        "moderate",
    ),
    "presentation/openapi_responses.py": (
        "Mô tả response OpenAPI chuẩn (401/403/404/422) và merge vào decorator route.",
        ["type-definition", "api-handler", "documentation"],
        "moderate",
    ),
    "presentation/routes/v1/__init__.py": (
        "Barrel gom tất cả APIRouter v1 (auth, cameras, dispatch, runtime, …) để mount vào app.",
        ["barrel", "entry-point", "api-handler"],
        "simple",
    ),
    "presentation/routes/v1/auth.py": (
        "Route đăng nhập, refresh, logout và `/me` — facade tới use case auth trong container.",
        ["api-handler", "security", "entry-point"],
        "simple",
    ),
    "presentation/routes/v1/cameras.py": (
        "API camera: WebRTC WHEP, preview, snapshot, ROI và cấu hình camera cho frontend.",
        ["api-handler", "service", "component"],
        "complex",
    ),
    "presentation/routes/v1/dispatch.py": (
        "Endpoint active tasks và SSE dispatch events cho luồng điều phối AMR.",
        ["api-handler", "event-handler", "service"],
        "simple",
    ),
    "presentation/routes/v1/external_server.py": (
        "Webhook unlock theo order status từ hệ thống bên ngoài (ICS/external server).",
        ["api-handler", "service", "validation"],
        "simple",
    ),
    "presentation/routes/v1/logs.py": (
        "Truy vấn audit log, user action log và system action log có phân quyền.",
        ["api-handler", "service", "security"],
        "simple",
    ),
    "presentation/routes/v1/maps.py": (
        "Import/quản lý bản đồ nén (map zip), phiên bản và tải file compress cho robot.",
        ["api-handler", "service", "serialization"],
        "moderate",
    ),
    "presentation/routes/v1/nodes.py": (
        "CRUD trạng thái node AMR: runtime view, maintenance, lock/unlock theo user.",
        ["api-handler", "service", "validation"],
        "moderate",
    ),
    "presentation/routes/v1/notifications.py": (
        "Danh sách thông báo và đánh dấu đã đọc (một hoặc tất cả).",
        ["api-handler", "service", "event-handler"],
        "simple",
    ),
    "presentation/routes/v1/pairs.py": (
        "Quản lý cặp camera–node (pair): list, tạo, sửa, xóa và bật/tắt.",
        ["api-handler", "service", "data-model"],
        "moderate",
    ),
    "presentation/routes/v1/poll.py": (
        "Long-poll snapshot tổng hợp cho FE (include flags) — giảm số request riêng lẻ.",
        ["api-handler", "service", "utility"],
        "simple",
    ),
    "presentation/routes/v1/runtime.py": (
        "Điều khiển runtime scan/dispatch: start, confirm, pending pairs, pause và SSE runtime.",
        ["api-handler", "service", "event-handler"],
        "moderate",
    ),
    "presentation/routes/v1/sandbox.py": (
        "API sandbox mô phỏng node/order cho dev/test, gọi RuntimeService và smoke trail.",
        ["api-handler", "test", "service"],
        "moderate",
    ),
    "presentation/routes/v1/snapshots.py": (
        "Phục vụ ảnh snapshot theo id hoặc theo order cho UI và audit.",
        ["api-handler", "service", "serialization"],
        "simple",
    ),
    "presentation/routes/v1/system.py": (
        "Health check và lệnh start/stop toàn bộ camera runtime (system scope).",
        ["api-handler", "service", "monitoring"],
        "simple",
    ),
    "presentation/routes/v1/zones.py": (
        "Liệt kê zone và start/stop camera theo vùng địa lý.",
        ["api-handler", "service", "validation"],
        "simple",
    ),
    "presentation/schemas.py": (
        "Pydantic payload/response cho toàn bộ REST v1: auth, camera, pair, node, sandbox, webhook.",
        ["type-definition", "validation", "api-handler"],
        "complex",
    ),
    "presentation/sse.py": (
        "Wrapper StreamingResponse cho Server-Sent Events với header cache/no-buffer phù hợp proxy.",
        ["utility", "event-handler", "api-handler"],
        "simple",
    ),
}

FN_OVERRIDES: dict[str, dict[str, tuple[str, list[str], str]]] = {
    "class:application/container.py:AppContainer": (
        "Container DI khởi tạo null port, bind adapter thật và wire use case FE/runtime/dispatch.",
        ["factory", "singleton", "service"],
        "complex",
    ),
    "function:domain/permissions.py:permissions_for_role": (
        "Trả về list permission string cho role (chuẩn hóa lowercase/strip).",
        ["security", "utility", "validation"],
        "simple",
    ),
    "function:presentation/deps.py:require_permission": (
        "Dependency factory kiểm tra user có permission trước khi vào route handler.",
        ["middleware", "security", "validation"],
        "moderate",
    ),
    "function:presentation/http_v1.py:data_or_error": (
        "Map UseCaseResult sang JSON hoặc HTTPException theo mã lỗi use case.",
        ["utility", "serialization", "api-handler"],
        "moderate",
    ),
    "function:presentation/sse.py:sse_response": (
        "Tạo StreamingResponse SSE từ async generator events.",
        ["event-handler", "utility", "api-handler"],
        "simple",
    ),
}

SCHEMA_CLASS_TAGS = ["type-definition", "validation", "api-schema"]


def complexity_from_lines(non_empty: int) -> str:
    if non_empty < 50:
        return "simple"
    if non_empty <= 200:
        return "moderate"
    return "complex"


def fn_complexity(start: int, end: int) -> str:
    n = end - start + 1
    if n < 15:
        return "simple"
    if n <= 40:
        return "moderate"
    return "complex"


def default_fn_summary(path: str, name: str) -> str:
    if path == "presentation/routes/v1/__init__.py":
        return "Đăng ký router con vào APIRouter v1."
    if path.startswith("presentation/routes/v1/"):
        action = name.replace("_", " ")
        return f"Handler FastAPI `{name}` — {action} qua container/use case."
    if path == "presentation/schemas.py":
        return f"Model Pydantic `{name}` cho body/query response API v1."
    if path == "presentation/openapi_responses.py":
        return f"Hỗ trợ mô tả OpenAPI: `{name}`."
    if path.startswith("application/container.py"):
        return f"Method `{name}` của AppContainer — bind/wire dependency hoặc runtime."
    return f"Hàm `{name}` trong `{path}`."


def default_fn_tags(path: str, name: str) -> list[str]:
    if path.startswith("presentation/routes"):
        return ["api-handler", "service", "validation"]
    if path == "presentation/deps.py":
        return ["middleware", "security", "utility"]
    if path == "presentation/schemas.py":
        return SCHEMA_CLASS_TAGS.copy()
    if path == "application/container.py":
        return ["factory", "service", "singleton"]
    return ["utility", "service", "validation"]


def is_significant_fn(fn: dict, exports: set[str]) -> bool:
    lines = fn["endLine"] - fn["startLine"] + 1
    return lines >= 10 or fn["name"] in exports


def is_significant_cls(cls: dict, exports: set[str]) -> bool:
    methods = len(cls.get("methods") or [])
    lines = cls["endLine"] - cls["startLine"] + 1
    return methods >= 2 or lines >= 20 or cls["name"] in exports


def load_neighbor_symbols(neighbor_map: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for _file, neighbors in neighbor_map.items():
        for nb in neighbors:
            p = nb["path"]
            syms = set(nb.get("symbols") or [])
            out.setdefault(p, set()).update(syms)
    return out


def resolve_call_target(callee: str, neighbor_syms: dict[str, set[str]], batch_paths: set[str]) -> str | None:
    """Map callGraph callee to function:/class: id when confident."""
    if "." in callee and not callee.startswith("("):
        parts = callee.split(".")
        if len(parts) == 2 and parts[0] == "container":
            sym = parts[1]
            for path, syms in neighbor_syms.items():
                if sym in syms:
                    return f"function:{path}:{sym}"
            if sym in ("AppContainer",):
                return "class:application/container.py:AppContainer"
        if parts[0] in ("HTTPException", "JSONResponse", "StreamingResponse"):
            return None
    base = callee.split("(")[0].strip()
    if base in ("HTTPException", "JSONResponse", "list", "dict", "set", "str", "int", "bool"):
        return None
    for path in batch_paths:
        if path.endswith(f"/{base}.py") or path == f"{base}.py":
            return f"file:{path}"
    for path, syms in neighbor_syms.items():
        if base in syms:
            kind = "class" if base[0].isupper() else "function"
            return f"{kind}:{path}:{base}"
    return None


def build_graph():
    inp = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    batches = json.loads(BATCHES_PATH.read_text(encoding="utf-8"))
    neighbor_map = next(b["neighborMap"] for b in batches["batches"] if b["batchIndex"] == BATCH_INDEX)
    batch_import = inp["batchImportData"]
    batch_paths = {f["path"] for f in inp["batchFiles"]}
    neighbor_syms = load_neighbor_symbols(neighbor_map)

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()
    sym_nodes: dict[str, str] = {}  # name -> id in batch (for calls)

    for fr in extract["results"]:
        path = fr["path"]
        exports = {e["name"] for e in fr.get("exports", [])}
        non_empty = fr.get("nonEmptyLines", fr.get("totalLines", 0))
        fsum, ftags, fcx = FILE_SUMMARIES.get(
            path,
            (f"Tệp mã `{path}`.", ["utility", "service", "validation"], complexity_from_lines(non_empty)),
        )
        if path in FILE_SUMMARIES:
            fcx = FILE_SUMMARIES[path][2]
        else:
            fcx = complexity_from_lines(non_empty)

        fid = f"file:{path}"
        nodes.append(
            {
                "id": fid,
                "type": "file",
                "name": path.split("/")[-1],
                "filePath": path,
                "summary": fsum,
                "tags": ftags[:5],
                "complexity": fcx,
            }
        )
        node_ids.add(fid)

        for cls in fr.get("classes", []):
            if not is_significant_cls(cls, exports):
                continue
            cid = f"class:{path}:{cls['name']}"
            key = cid
            if key in FN_OVERRIDES:
                cs, ct, cc = FN_OVERRIDES[key]
            elif path == "presentation/schemas.py":
                cs = default_fn_summary(path, cls["name"])
                ct = SCHEMA_CLASS_TAGS.copy()
                cc = fn_complexity(cls["startLine"], cls["endLine"])
            else:
                cs = default_fn_summary(path, cls["name"])
                ct = default_fn_tags(path, cls["name"])
                cc = fn_complexity(cls["startLine"], cls["endLine"])
            nodes.append(
                {
                    "id": cid,
                    "type": "class",
                    "name": cls["name"],
                    "filePath": path,
                    "lineRange": [cls["startLine"], cls["endLine"]],
                    "summary": cs,
                    "tags": ct[:5],
                    "complexity": cc,
                }
            )
            node_ids.add(cid)
            sym_nodes[cls["name"]] = cid
            edges.append(
                {"source": fid, "target": cid, "type": "contains", "direction": "forward", "weight": 1.0}
            )
            if cls["name"] in exports:
                edges.append(
                    {"source": fid, "target": cid, "type": "exports", "direction": "forward", "weight": 0.8}
                )

        for fn in fr.get("functions", []):
            if not is_significant_fn(fn, exports):
                continue
            fnid = f"function:{path}:{fn['name']}"
            key = fnid
            if key in FN_OVERRIDES:
                fs, ft, fc = FN_OVERRIDES[key]
            else:
                fs = default_fn_summary(path, fn["name"])
                ft = default_fn_tags(path, fn["name"])
                fc = fn_complexity(fn["startLine"], fn["endLine"])
            nodes.append(
                {
                    "id": fnid,
                    "type": "function",
                    "name": fn["name"],
                    "filePath": path,
                    "lineRange": [fn["startLine"], fn["endLine"]],
                    "summary": fs,
                    "tags": ft[:5],
                    "complexity": fc,
                }
            )
            node_ids.add(fnid)
            sym_nodes[fn["name"]] = fnid
            edges.append(
                {"source": fid, "target": fnid, "type": "contains", "direction": "forward", "weight": 1.0}
            )
            if fn["name"] in exports:
                edges.append(
                    {"source": fid, "target": fnid, "type": "exports", "direction": "forward", "weight": 0.8}
                )

    import_count = 0
    for file_path, targets in batch_import.items():
        src = f"file:{file_path}"
        for tgt in targets:
            edges.append(
                {
                    "source": src,
                    "target": f"file:{tgt}",
                    "type": "imports",
                    "direction": "forward",
                    "weight": 0.7,
                }
            )
            import_count += 1

    seen_calls: set[tuple[str, str]] = set()
    for fr in extract["results"]:
        path = fr["path"]
        for cg in fr.get("callGraph", []):
            caller = cg["caller"]
            caller_id = sym_nodes.get(caller) or f"function:{path}:{caller}"
            if caller_id not in node_ids:
                continue
            tgt = resolve_call_target(cg["callee"], neighbor_syms, batch_paths)
            if not tgt or tgt == caller_id:
                continue
            pair = (caller_id, tgt)
            if pair in seen_calls:
                continue
            seen_calls.add(pair)
            edges.append(
                {"source": caller_id, "target": tgt, "type": "calls", "direction": "forward", "weight": 0.8}
            )

    return nodes, edges, import_count


def write_output(nodes: list[dict], edges: list[dict], import_count: int):
    node_count = len(nodes)
    edge_count = len(edges)
    out = OUT_DIR / f"batch-{BATCH_INDEX}.json"
    fragment = {"nodes": nodes, "edges": edges}
    out.write_text(json.dumps(fragment, ensure_ascii=False, indent=2), encoding="utf-8")
    return [out], node_count, edge_count, import_count


def main():
    nodes, edges, import_count = build_graph()
    expected = sum(len(v) for v in json.loads(INPUT_PATH.read_text(encoding="utf-8"))["batchImportData"].values())
    assert import_count == expected, f"imports {import_count} != {expected}"
    written, nc, ec, ic = write_output(nodes, edges, import_count)
    print(
        json.dumps(
            {
                "files_written": [str(p) for p in written],
                "nodes": nc,
                "edges": ec,
                "imports_edges": ic,
                "imports_expected": expected,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
