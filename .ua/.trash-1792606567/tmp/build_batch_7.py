# -*- coding: utf-8 -*-
"""Generate batch-7.json GraphFragment for Understand-Anything."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(r"d:\Prj\kortek")
UA = ROOT / ".ua"
EXTRACT_PATH = UA / "tmp" / "ua-file-extract-results-7.json"
INPUT_PATH = UA / "tmp" / "ua-file-analyzer-input-7.json"
BATCHES_PATH = UA / "intermediate" / "batches.json"
OUT_PATH = UA / "intermediate" / "batch-7.json"
BATCH_INDEX = 7

FILE_SUMMARIES: dict[str, tuple[str, list[str], str, str | None]] = {
    "application/dispatch/active_task_hub.py": (
        "Hub in-memory thread-safe cho danh sách active task dispatch: upsert, SSE subscribe qua queue.",
        ["dispatch", "hub", "sse", "thread-safe", "active-tasks"],
        "moderate",
        "Lock + Queue fan-out snapshot mỗi khi state đổi.",
    ),
    "application/dispatch/active_tasks.py": (
        "Use case dispatch: đọc priority, track task sau dispatch, list active tasks và unlock theo order status ICS.",
        ["use-case", "dispatch", "active-tasks", "ics-unlock", "application-layer"],
        "moderate",
        None,
    ),
    "application/null_ports.py": (
        "Null Object implementations cho mọi application port — dùng khi chưa wire infrastructure (test/offline).",
        ["null-object", "ports", "test-double", "dependency-injection", "stub"],
        "complex",
        "NullNodeStateStore gọi ResetResult từ reset_policy.",
    ),
    "domain/dispatch/active_task.py": (
        "Pure helpers build/sort ActiveTask view từ order_id, status và StartMeta priority.",
        ["domain", "active-task", "dispatch", "pure-logic", "sort"],
        "simple",
        None,
    ),
    "domain/models.py": (
        "Dataclass/enum lõi domain: NodeType, OrderStatus, DispatchPair, RuntimeStatus cho AMR dispatch.",
        ["domain", "data-model", "enum", "dataclass", "amr"],
        "simple",
        None,
    ),
    "domain/reset_policy.py": (
        "Luật reset flag/lock node khi order ICS đổi trạng thái (clears_order) — trả ResetResult.",
        ["domain", "reset", "order-status", "node-lock", "pure-logic"],
        "moderate",
        None,
    ),
    "infrastructure/adapters.py": (
        "Adapter bọc CameraManager, InferenceEngine, StateManager và RuntimeService thành application ports.",
        ["adapter", "hexagonal", "infrastructure", "ports", "runtime"],
        "complex",
        "NodeStateAdapter.apply_reset gọi reset_flags_by_order.",
    ),
    "infrastructure/sandbox/sandbox_ics.py": (
        "ICS giả lập in-memory: send dispatch, lưu order status cho sandbox API và smoke trail.",
        ["sandbox", "ics", "mock", "dispatch", "test"],
        "moderate",
        None,
    ),
}

SYMBOL_OVERRIDES: dict[str, tuple[str, list[str], str]] = {
    "class:application/dispatch/active_task_hub.py:ActiveTaskHub": (
        "Store dict order_id→task, publish snapshot cho subscriber SSE.",
        ["hub", "dispatch", "observer", "thread-safe"],
        "moderate",
    ),
    "class:application/dispatch/active_tasks.py:GetActiveTasks": (
        "Đồng bộ hub với ICS order list + priority reader; trả UseCaseResult list task.",
        ["use-case", "active-tasks", "sync", "ics"],
        "moderate",
    ),
    "class:application/dispatch/active_tasks.py:UnlockByOrderStatus": (
        "Webhook path: xóa task hoặc cập nhật status và reset flags khi order hoàn tất.",
        ["use-case", "unlock", "order-status", "reset"],
        "moderate",
    ),
    "class:application/dispatch/active_tasks.py:TrackDispatchedTask": (
        "Sau dispatch thành công — build ActiveTask và upsert vào hub.",
        ["use-case", "track", "dispatch", "hub"],
        "simple",
    ),
    "class:application/dispatch/active_tasks.py:StartPriorityReader": (
        "Đọc StartMetaMap từ NodeRepository + runtime meta cho sort active tasks.",
        ["use-case", "priority", "reader", "start-meta"],
        "simple",
    ),
    "class:infrastructure/adapters.py:NodeStateAdapter": (
        "Port NodeStateStore: delegate StateManager, sync lock Mongo qua NodeLockSync, apply reset policy.",
        ["adapter", "node-state", "lock-sync", "reset"],
        "complex",
    ),
    "class:infrastructure/sandbox/sandbox_ics.py:SandboxIcs": (
        "DispatchGateway + IcsOrderQuery sandbox: log send, emit smoke trail, dict orders thread-safe.",
        ["sandbox", "ics", "gateway", "mock"],
        "moderate",
    ),
    "function:domain/dispatch/active_task.py:build_active_task": (
        "Ghép parse_order_id, status label và priority từ StartMeta thành dict UI.",
        ["active-task", "builder", "domain"],
        "simple",
    ),
    "function:domain/dispatch/active_task.py:sort_active_tasks": (
        "Sắp xếp task theo resolve_priority và start_sort_key.",
        ["sort", "priority", "domain"],
        "simple",
    ),
    "function:domain/reset_policy.py:reset_flags_by_order": (
        "Entry reset: tra order_mapping, clears_order → _reset_all cặp liên quan.",
        ["reset", "order-status", "domain"],
        "moderate",
    ),
    "class:domain/reset_policy.py:ResetResult": (
        "Kết quả reset: success, message, danh sách cặp đã clear.",
        ["data-model", "reset", "domain"],
        "simple",
    ),
    "class:domain/models.py:OrderStatus": (
        "Enum trạng thái order ICS; clears_order() xác định khi nào gỡ task/reset node.",
        ["enum", "order-status", "ics", "domain"],
        "simple",
    ),
}


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


def is_significant_fn(fn: dict, exports: set[str]) -> bool:
    lines = fn["endLine"] - fn["startLine"] + 1
    return lines >= 10 or fn["name"] in exports


def is_significant_cls(cls: dict, exports: set[str]) -> bool:
    methods = len(cls.get("methods") or [])
    lines = cls["endLine"] - cls["startLine"] + 1
    return methods >= 2 or lines >= 20 or cls["name"] in exports


def default_class_summary(path: str, name: str) -> str:
    if path == "application/null_ports.py" and name.startswith("Null"):
        return f"Stub port `{name}` — no-op hoặc raise khi gọi ngoài phạm vi test."
    if path == "application/dispatch/active_tasks.py":
        return f"Use case / helper `{name}` trong luồng active task dispatch."
    if path == "infrastructure/adapters.py":
        return f"Adapter `{name}` — delegate sang infrastructure runtime tương ứng."
    if path == "domain/models.py":
        return f"Model domain `{name}` dùng chung dispatch và runtime."
    return f"Class `{name}` trong `{path}`."


def default_fn_summary(path: str, name: str) -> str:
    if name.startswith("_"):
        return f"Hàm nội bộ `{name}` — hỗ trợ logic trong module."
    return f"Hàm `{name}` trong `{path}`."


def default_tags(path: str, name: str) -> list[str]:
    if path == "application/null_ports.py":
        return ["null-object", "stub", "ports"]
    if path.startswith("domain/"):
        return ["domain", "pure-logic", "dispatch"]
    if path.startswith("application/dispatch"):
        return ["use-case", "dispatch", "application-layer"]
    if path.startswith("infrastructure/"):
        return ["adapter", "infrastructure", "service"]
    return ["utility", "python", "kortek"]


def load_neighbor_symbols(neighbor_map: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for neighbors in neighbor_map.values():
        for nb in neighbors:
            p = nb["path"]
            syms = set(nb.get("symbols") or [])
            out.setdefault(p, set()).update(syms)
    return out


def normalize_callee(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^self\.", "", s)
    if "." in s and not s.startswith("("):
        s = s.split(".")[-1]
    s = re.split(r"\(", s, maxsplit=1)[0]
    return s.strip()


def resolve_call_target(
    callee_norm: str,
    neighbor_syms: dict[str, set[str]],
    batch_paths: set[str],
    sym_nodes: dict[str, str],
) -> str | None:
    if callee_norm in sym_nodes:
        return sym_nodes[callee_norm]
    for path, syms in neighbor_syms.items():
        if callee_norm in syms:
            kind = "class" if callee_norm[0].isupper() else "function"
            return f"{kind}:{path}:{callee_norm}"
    skip = {
        "dict",
        "list",
        "set",
        "str",
        "int",
        "len",
        "sorted",
        "bool",
        "getattr",
        "hasattr",
        "threading",
        "asyncio",
        "RuntimeError",
        "reversed",
        "queue",
        "logger",
        "time",
    }
    if callee_norm in skip or not callee_norm:
        return None
    if callee_norm == "OrderStatus":
        return "class:domain/models.py:OrderStatus"
    if callee_norm == "clears_order":
        return None
    for path in batch_paths:
        if path.endswith(f"/{callee_norm}.py"):
            return f"file:{path}"
    return None


def symbol_meta(node_id: str, path: str, name: str, start: int, end: int, ntype: str) -> tuple[str, list[str], str]:
    if node_id in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[node_id]
    if ntype == "class":
        return (
            default_class_summary(path, name),
            default_tags(path, name),
            fn_complexity(start, end),
        )
    return (
        default_fn_summary(path, name),
        default_tags(path, name),
        fn_complexity(start, end),
    )


def build_graph() -> tuple[list[dict], list[dict], int]:
    inp = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    batches = json.loads(BATCHES_PATH.read_text(encoding="utf-8"))
    batch = next(b for b in batches["batches"] if b["batchIndex"] == BATCH_INDEX)
    neighbor_map = batch["neighborMap"]
    batch_import = inp["batchImportData"]
    batch_paths = {f["path"] for f in inp["batchFiles"]}
    neighbor_syms = load_neighbor_symbols(neighbor_map)

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()
    sym_nodes: dict[str, str] = {}
    fn_by_path_name: dict[tuple[str, str], str] = {}
    cls_by_path_name: dict[tuple[str, str], str] = {}
    method_to_class: dict[tuple[str, str], str] = {}

    for fr in extract["results"]:
        path = fr["path"]
        exports = {e["name"] for e in fr.get("exports", [])}
        for fn in fr.get("functions", []):
            if not is_significant_fn(fn, exports):
                continue
            nid = f"function:{path}:{fn['name']}"
            fn_by_path_name[(path, fn["name"])] = nid
            sym_nodes[fn["name"]] = nid
        for cls in fr.get("classes", []):
            if not is_significant_cls(cls, exports):
                continue
            cid = f"class:{path}:{cls['name']}"
            cls_by_path_name[(path, cls["name"])] = cid
            sym_nodes[cls["name"]] = cid
            for m in cls.get("methods") or []:
                if m.startswith("_") and m not in ("__init__",):
                    continue
                method_to_class[(path, m)] = cid

    for fr in extract["results"]:
        path = fr["path"]
        exports = {e["name"] for e in fr.get("exports", [])}
        non_empty = fr.get("nonEmptyLines", fr.get("totalLines", 0))
        fsum, ftags, fcx, lnotes = FILE_SUMMARIES.get(
            path,
            (f"Module `{path}`.", ["python", "kortek"], complexity_from_lines(non_empty), None),
        )
        if path not in FILE_SUMMARIES:
            fcx = complexity_from_lines(non_empty)

        fid = f"file:{path}"
        file_node: dict[str, Any] = {
            "id": fid,
            "type": "file",
            "name": path.split("/")[-1],
            "filePath": path,
            "summary": fsum,
            "tags": ftags[:5],
            "complexity": fcx,
        }
        if lnotes:
            file_node["languageNotes"] = lnotes
        nodes.append(file_node)
        node_ids.add(fid)

        for cls in fr.get("classes", []):
            if not is_significant_cls(cls, exports):
                continue
            cid = f"class:{path}:{cls['name']}"
            cs, ct, cc = symbol_meta(cid, path, cls["name"], cls["startLine"], cls["endLine"], "class")
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
            fs, ft, fc = symbol_meta(fnid, path, fn["name"], fn["startLine"], fn["endLine"], "function")
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

    skip_callees = {
        "dict",
        "list",
        "set",
        "str",
        "int",
        "len",
        "sorted",
        "bool",
        "getattr",
        "hasattr",
        "threading",
        "asyncio",
        "RuntimeError",
        "reversed",
        "queue",
        "logger",
        "time",
        "append",
        "get",
        "items",
        "values",
        "pop",
        "discard",
        "split",
        "isdigit",
    }
    seen_calls: set[tuple[str, str]] = set()
    for fr in extract["results"]:
        path = fr["path"]
        for cg in fr.get("callGraph", []):
            caller = cg["caller"]
            callee_norm = normalize_callee(cg["callee"])
            if not callee_norm or callee_norm in skip_callees:
                continue

            src = method_to_class.get((path, caller))
            if not src:
                src = fn_by_path_name.get((path, caller))
            if not src or src not in node_ids:
                continue

            tgt = fn_by_path_name.get((path, callee_norm))
            if not tgt:
                tgt = cls_by_path_name.get((path, callee_norm))
            if not tgt:
                tgt = resolve_call_target(callee_norm, neighbor_syms, batch_paths, sym_nodes)
            if not tgt or tgt == src:
                continue

            pair = (src, tgt)
            if pair in seen_calls:
                continue
            seen_calls.add(pair)
            edges.append(
                {"source": src, "target": tgt, "type": "calls", "direction": "forward", "weight": 0.8}
            )

    return nodes, edges, import_count


def main() -> None:
    nodes, edges, import_count = build_graph()
    expected = sum(len(v) for v in json.loads(INPUT_PATH.read_text(encoding="utf-8"))["batchImportData"].values())
    assert import_count == expected, f"imports {import_count} != {expected}"
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2), encoding="utf-8")
    calls = sum(1 for e in edges if e["type"] == "calls")
    print(
        json.dumps(
            {
                "output": str(OUT_PATH),
                "nodes": len(nodes),
                "edges": len(edges),
                "imports": import_count,
                "calls_edges": calls,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
