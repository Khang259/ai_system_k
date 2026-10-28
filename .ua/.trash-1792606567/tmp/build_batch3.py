# -*- coding: utf-8 -*-
"""Generate batch-3.json for Understand-Anything."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(r"d:\Prj\kortek")
EXTRACT = ROOT / ".ua" / "tmp" / "ua-file-extract-results-3.json"
INPUT = ROOT / ".ua" / "tmp" / "ua-file-analyzer-input-3.json"
OUTPUT = ROOT / ".ua" / "intermediate" / "batch-3.json"

FILE_META: Dict[str, Dict[str, Any]] = {
    "application/cameras/webrtc_ice.py": {
        "summary": "Helper WebRTC ICE/STUN/TURN từ settings cho browser và MediaMTX.",
        "complexity": "simple",
        "tags": ["webrtc", "ice", "stun-turn", "camera"],
        "languageNotes": "Đọc WEBRTC_* từ config.settings.",
    },
    "application/dispatch/dispatch_service.py": {
        "summary": "Application service gửi lệnh ICS (single/empty/double), ghép cặp và audit callback.",
        "complexity": "complex",
        "tags": ["dispatch", "ics", "application-layer", "pairing"],
        "languageNotes": "Không thread; PairManager gọi trong loop.",
    },
    "application/dispatch/ics_payload.py": {
        "summary": "Dựng JSON payload outbound ICS theo loại dispatch và settings.",
        "complexity": "moderate",
        "tags": ["ics", "payload", "dispatch", "json"],
        "languageNotes": "Pure builder, không HTTP.",
    },
    "application/dispatch/pending_pairs.py": {
        "summary": "Use case xem trước cặp dispatch tiếp theo cho FE trước confirm.",
        "complexity": "moderate",
        "tags": ["pending-pairs", "use-case", "scan-session", "fe-preview"],
        "languageNotes": "Trả UseCaseResult; dùng batch_policy và pairing domain.",
    },
    "application/runtime/runtime_service.py": {
        "summary": "Composition root: khởi động/dừng camera, inference, PairManager và NodeState.",
        "complexity": "complex",
        "tags": ["runtime", "lifespan", "composition-root", "startup"],
        "languageNotes": "Wire sandbox hoặc production từ settings.SANDBOX_MODE.",
    },
    "config/settings.py": {
        "summary": "Pydantic Settings đọc env/.env — ICS, Mongo, WebRTC, sandbox, retention.",
        "complexity": "moderate",
        "tags": ["settings", "pydantic", "env-config", "fastapi"],
        "languageNotes": "Kế thừa domain settings constants.",
    },
    "domain/dispatch/__init__.py": {
        "summary": "Barrel re-export pairing và priority helpers.",
        "complexity": "simple",
        "tags": ["barrel", "dispatch-domain", "re-export"],
        "languageNotes": "Package domain.dispatch.",
    },
    "domain/dispatch/pairing.py": {
        "summary": "Luật ghép cặp start/end thuần domain từ ready sets và validate_pairs.",
        "complexity": "moderate",
        "tags": ["pairing", "domain", "pure-logic", "priority-sort"],
        "languageNotes": "Không ICS/HTTP/thread.",
    },
    "domain/dispatch/priority.py": {
        "summary": "Sắp xếp start node theo priority Mongo và build StartMetaMap.",
        "complexity": "simple",
        "tags": ["priority", "start-meta", "domain", "sort-key"],
        "languageNotes": "PRIORITY_FALLBACK từ domain.settings.",
    },
    "domain/node_state.py": {
        "summary": "In-memory trạng thái node/pair, lock và refresh cho dispatch loop.",
        "complexity": "complex",
        "tags": ["node-state", "domain", "lock", "runtime-state"],
        "languageNotes": "NodeState là core state machine cho AMR nodes.",
    },
    "domain/settings.py": {
        "summary": "Hằng số domain (priority fallback) tách khỏi config env.",
        "complexity": "simple",
        "tags": ["domain-constants", "priority", "shared"],
        "languageNotes": "Không phụ thuộc Pydantic.",
    },
    "infrastructure/auth/notification_publisher.py": {
        "summary": "Port publish notification SSE; Null impl khi tắt.",
        "complexity": "simple",
        "tags": ["notification", "sse", "auth-infra", "null-object"],
        "languageNotes": "bind_loop gắn asyncio loop.",
    },
    "infrastructure/dispatch/__init__.py": {
        "summary": "Barrel export PairManager và strategy dispatch.",
        "complexity": "simple",
        "tags": ["barrel", "dispatch-infra", "pair-manager"],
        "languageNotes": "",
    },
    "infrastructure/dispatch/pair_manager.py": {
        "summary": "Thread loop ~1s gọi DispatchService qua strategy single/empty/double.",
        "complexity": "complex",
        "tags": ["pair-manager", "thread", "strategy-pattern", "dispatch-loop"],
        "languageNotes": "Infrastructure bọc application DispatchService.",
    },
    "infrastructure/ics/__init__.py": {
        "summary": "Barrel HTTP gateway và order query ICS.",
        "complexity": "simple",
        "tags": ["barrel", "ics", "http-client"],
        "languageNotes": "",
    },
    "infrastructure/ics/http_dispatch_gateway.py": {
        "summary": "POST payload sang ICS_URL qua httpx; implement DispatchGateway port.",
        "complexity": "moderate",
        "tags": ["ics", "http", "gateway", "outbound"],
        "languageNotes": "Audit/log lỗi qua setup_logger.",
    },
    "infrastructure/ics/http_order_query.py": {
        "summary": "GET trạng thái order ICS; implement IcsOrderQueryPort.",
        "complexity": "simple",
        "tags": ["ics", "order-query", "http", "port"],
        "languageNotes": "",
    },
    "infrastructure/persistence/node_lock_sync.py": {
        "summary": "Đồng bộ lock node với Mongo; Null khi không cần persist lock.",
        "complexity": "moderate",
        "tags": ["node-lock", "mongodb", "persistence", "sync"],
        "languageNotes": "",
    },
    "infrastructure/sandbox/__init__.py": {
        "summary": "Barrel sandbox camera, ICS, inference cho SANDBOX_MODE.",
        "complexity": "simple",
        "tags": ["sandbox", "barrel", "dev-mode"],
        "languageNotes": "Re-export từ sandbox_* modules.",
    },
    "infrastructure/sandbox/sandbox_camera_manager.py": {
        "summary": "CameraManager giả lập frame/video cho dev không GPU.",
        "complexity": "moderate",
        "tags": ["sandbox", "camera", "mock", "dev"],
        "languageNotes": "Delegate pattern từ CameraManager base.",
    },
    "infrastructure/sandbox/sandbox_inference.py": {
        "summary": "InferencePort trả detection giả cho pipeline sandbox.",
        "complexity": "simple",
        "tags": ["sandbox", "inference", "mock", "vision"],
        "languageNotes": "",
    },
    "infrastructure/storage/__init__.py": {
        "summary": "Barrel map zip store và retention runner.",
        "complexity": "simple",
        "tags": ["storage", "barrel", "maps", "retention"],
        "languageNotes": "",
    },
    "infrastructure/storage/map_zip_store.py": {
        "summary": "Đọc/ghi file map .zip và validate entry nén.",
        "complexity": "moderate",
        "tags": ["map-zip", "storage", "filesystem", "validation"],
        "languageNotes": "",
    },
    "infrastructure/storage/retention.py": {
        "summary": "Xóa log/snapshot cũ theo TTL; RetentionRunner chạy nền.",
        "complexity": "moderate",
        "tags": ["retention", "cleanup", "logs", "background"],
        "languageNotes": "purge_old_logs quét thư mục logs.",
    },
}

SYMBOL_META: Dict[str, Dict[str, Any]] = {
    "function:application/cameras/webrtc_ice.py:ice_servers_for_browser": {
        "summary": "Trả danh sách ICE servers cho trình duyệt WebRTC (STUN/TURN + credential).",
        "complexity": "simple",
        "tags": ["webrtc", "browser", "ice", "stun"],
    },
    "function:application/cameras/webrtc_ice.py:ice_servers_for_mediamtx": {
        "summary": "Format ICE servers cho MediaMTX (username/credential riêng).",
        "complexity": "simple",
        "tags": ["webrtc", "mediamtx", "ice", "turn"],
    },
    "class:application/dispatch/dispatch_service.py:DispatchService": {
        "summary": "Orchestrate dispatch_single/empty/double, build_pairs và callback audit/task.",
        "complexity": "complex",
        "tags": ["dispatch-service", "ics", "callbacks", "application"],
    },
    "function:application/dispatch/ics_payload.py:_digits": {
        "summary": "Lọc chuỗi chỉ giữ chữ số cho order id ICS.",
        "complexity": "simple",
        "tags": ["helper", "ics", "sanitize"],
    },
    "function:application/dispatch/ics_payload.py:build_single_payload": {
        "summary": "Payload ICS cho dispatch single (start→end).",
        "complexity": "moderate",
        "tags": ["ics", "payload", "single-dispatch"],
    },
    "function:application/dispatch/ics_payload.py:build_empty_payload": {
        "summary": "Payload ICS cho empty dispatch tới END_POINT_EMPTY.",
        "complexity": "moderate",
        "tags": ["ics", "payload", "empty-dispatch"],
    },
    "function:application/dispatch/ics_payload.py:build_double_payload": {
        "summary": "Payload ICS gom hai cặp trong một lệnh double.",
        "complexity": "moderate",
        "tags": ["ics", "payload", "double-dispatch"],
    },
    "class:application/dispatch/pending_pairs.py:GetPendingPairs": {
        "summary": "execute() tính readyStarts, nextPairs và trạng thái batch cho UI.",
        "complexity": "moderate",
        "tags": ["use-case", "pending", "fe-api", "preview"],
    },
    "class:application/runtime/runtime_service.py:RuntimeService": {
        "summary": "start/stop toàn bộ runtime: repos, vision, dispatch thread, snapshot store.",
        "complexity": "complex",
        "tags": ["runtime", "startup", "shutdown", "wiring"],
    },
    "class:config/settings.py:Settings": {
        "summary": "Central config: DB, ICS, WebRTC, paths, sandbox flags từ environment.",
        "complexity": "moderate",
        "tags": ["settings", "pydantic", "env", "config"],
    },
    "function:domain/dispatch/pairing.py:build_dispatch_pairs": {
        "summary": "Ghép start/end theo validate_pairs, sort priority, mỗi node dùng một lần.",
        "complexity": "moderate",
        "tags": ["pairing", "algorithm", "domain", "dispatch"],
    },
    "function:domain/dispatch/priority.py:resolve_priority": {
        "summary": "Chuẩn hóa priority Mongo sang int với fallback.",
        "complexity": "simple",
        "tags": ["priority", "parse", "domain"],
    },
    "function:domain/dispatch/priority.py:start_meta_from_docs": {
        "summary": "Build map node_id→{priority, zone_id} từ node documents.",
        "complexity": "moderate",
        "tags": ["start-meta", "mongodb", "domain"],
    },
    "function:domain/dispatch/priority.py:start_sort_key": {
        "summary": "Tuple sort key: priority ASC, zone_id, node_id cho ready starts.",
        "complexity": "simple",
        "tags": ["sort", "priority", "start-node"],
    },
    "function:domain/node_state.py:_refresh_flag": {
        "summary": "Helper cập nhật cờ refresh trên node entry.",
        "complexity": "simple",
        "tags": ["node-state", "helper", "flag"],
    },
    "function:domain/node_state.py:_is_blocked": {
        "summary": "Kiểm tra node bị block bởi lock hoặc trạng thái.",
        "complexity": "simple",
        "tags": ["node-state", "block", "helper"],
    },
    "class:domain/node_state.py:NodeState": {
        "summary": "Quản lý ready lists, locks, pairs đang chạy và transition dispatch.",
        "complexity": "complex",
        "tags": ["node-state", "state-machine", "dispatch", "lock"],
    },
    "class:infrastructure/auth/notification_publisher.py:NotificationPublisher": {
        "summary": "Gắn asyncio loop và publish event tới SSE subscribers.",
        "complexity": "simple",
        "tags": ["notification", "sse", "publisher"],
    },
    "class:infrastructure/auth/notification_publisher.py:NullNotificationPublisher": {
        "summary": "No-op publisher khi feature notification tắt.",
        "complexity": "simple",
        "tags": ["null-object", "notification", "stub"],
    },
    "function:infrastructure/dispatch/pair_manager.py:get_validate_pairs": {
        "summary": "Factory/helper lấy validate pairs từ repository (test hook).",
        "complexity": "simple",
        "tags": ["pair-manager", "helper", "pairs"],
    },
    "class:infrastructure/dispatch/pair_manager.py:DispatchStrategy": {
        "summary": "ABC strategy bọc DispatchService.execute theo loại dispatch.",
        "complexity": "moderate",
        "tags": ["strategy", "abc", "dispatch"],
    },
    "class:infrastructure/dispatch/pair_manager.py:SingleDispatch": {
        "summary": "Strategy gọi dispatch_single cho runtime mặc định.",
        "complexity": "moderate",
        "tags": ["single-dispatch", "strategy"],
    },
    "class:infrastructure/dispatch/pair_manager.py:EmptyDispatch": {
        "summary": "Strategy xử lý hàng đợi empty tới END_POINT_EMPTY.",
        "complexity": "moderate",
        "tags": ["empty-dispatch", "strategy"],
    },
    "class:infrastructure/dispatch/pair_manager.py:DoubleDispatch": {
        "summary": "Strategy gửi hai cặp trong một vòng double dispatch.",
        "complexity": "moderate",
        "tags": ["double-dispatch", "strategy"],
    },
    "class:infrastructure/dispatch/pair_manager.py:PairManager": {
        "summary": "Thread nền poll state và delegate strategy mỗi interval.",
        "complexity": "complex",
        "tags": ["pair-manager", "thread", "loop", "dispatch"],
    },
    "class:infrastructure/ics/http_dispatch_gateway.py:HttpDispatchGateway": {
        "summary": "httpx POST JSON tới ICS; timeout và log lỗi HTTP.",
        "complexity": "moderate",
        "tags": ["http", "ics", "gateway", "httpx"],
    },
    "class:infrastructure/ics/http_order_query.py:HttpOrderQuery": {
        "summary": "Query order status từ ICS REST endpoint.",
        "complexity": "simple",
        "tags": ["ics", "order", "query", "http"],
    },
    "class:infrastructure/persistence/node_lock_sync.py:NodeLockSync": {
        "summary": "Persist/clear node locks trên Mongo đồng bộ với NodeState.",
        "complexity": "moderate",
        "tags": ["mongodb", "lock", "sync", "persistence"],
    },
    "class:infrastructure/persistence/node_lock_sync.py:NullNodeLockSync": {
        "summary": "Bỏ qua persist lock — dùng khi chỉ in-memory.",
        "complexity": "simple",
        "tags": ["null-object", "lock", "stub"],
    },
    "class:infrastructure/sandbox/sandbox_camera_manager.py:SandboxCameraManager": {
        "summary": "Phát frame test/video thay camera thật trong sandbox mode.",
        "complexity": "moderate",
        "tags": ["sandbox", "camera", "mock-stream"],
    },
    "class:infrastructure/sandbox/sandbox_inference.py:SandboxInference": {
        "summary": "Trả detection cố định/giả lập cho pipeline không TensorRT.",
        "complexity": "simple",
        "tags": ["sandbox", "inference", "mock"],
    },
    "function:infrastructure/storage/map_zip_store.py:find_compress_entry": {
        "summary": "Tìm entry .compress trong zip map archive.",
        "complexity": "simple",
        "tags": ["zip", "map", "helper"],
    },
    "function:infrastructure/storage/map_zip_store.py:validate_zip_has_compress": {
        "summary": "Validate cấu trúc zip map trước khi lưu/serve.",
        "complexity": "moderate",
        "tags": ["validation", "zip", "map"],
    },
    "class:infrastructure/storage/map_zip_store.py:MapZipStore": {
        "summary": "CRUD file map .zip trên filesystem với kiểm tra compress.",
        "complexity": "moderate",
        "tags": ["map-store", "filesystem", "zip"],
    },
    "function:infrastructure/storage/retention.py:purge_old_logs": {
        "summary": "Xóa file log cũ hơn retention days trong thư mục cấu hình.",
        "complexity": "moderate",
        "tags": ["retention", "logs", "cleanup"],
    },
    "class:infrastructure/storage/retention.py:RetentionRunner": {
        "summary": "Thread/async runner gọi purge theo chu kỳ settings.",
        "complexity": "moderate",
        "tags": ["retention", "background", "scheduler"],
    },
}


def is_significant_function(fn: dict, export_names: Set[str]) -> bool:
    lines = fn["endLine"] - fn["startLine"] + 1
    return lines >= 10 or fn["name"] in export_names


def is_significant_class(cls: dict, export_names: Set[str]) -> bool:
    lines = cls["endLine"] - cls["startLine"] + 1
    methods = cls.get("methods") or []
    return len(methods) >= 2 or lines >= 20 or cls["name"] in export_names


def make_node(
    node_id: str,
    ntype: str,
    name: str,
    path: str,
    meta: Dict[str, Any],
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> dict:
    node = {
        "id": node_id,
        "type": ntype,
        "name": name,
        "path": path,
        "summary": meta.get("summary", ""),
        "complexity": meta.get("complexity", "moderate"),
        "tags": meta.get("tags", ["python", "kortek", "backend"])[:5],
    }
    ln = meta.get("languageNotes")
    if ln:
        node["languageNotes"] = ln
    if start_line is not None:
        node["startLine"] = start_line
    if end_line is not None:
        node["endLine"] = end_line
    return node


def normalize_callee(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^self\.", "", s)
    s = re.sub(r"^cls\.", "", s)
    if "." in s:
        s = s.split(".")[-1]
    s = re.split(r"\(", s, maxsplit=1)[0]
    return s.strip()


def main() -> None:
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    inp = json.loads(INPUT.read_text(encoding="utf-8"))
    batch_import: Dict[str, List[str]] = inp["batchImportData"]

    nodes: List[dict] = []
    edges: List[dict] = []
    node_ids: Set[str] = set()

    # Index symbols in batch
    fn_by_path_name: Dict[Tuple[str, str], str] = {}
    cls_by_path_name: Dict[Tuple[str, str], str] = {}
    method_to_class: Dict[Tuple[str, str], str] = {}
    global_fn_names: Dict[str, str] = {}

    for r in extract["results"]:
        path = r["path"]
        exports = {e["name"] for e in r.get("exports", [])}
        for fn in r.get("functions", []):
            if not is_significant_function(fn, exports):
                continue
            nid = f"function:{path}:{fn['name']}"
            fn_by_path_name[(path, fn["name"])] = nid
            global_fn_names[fn["name"]] = nid
        for cls in r.get("classes", []):
            if not is_significant_class(cls, exports):
                continue
            cid = f"class:{path}:{cls['name']}"
            cls_by_path_name[(path, cls["name"])] = cid
            for m in cls.get("methods") or []:
                if m.startswith("_") and m not in ("__init__",):
                    continue
                method_to_class[(path, m)] = cid

    def add_node(node: dict) -> None:
        if node["id"] not in node_ids:
            nodes.append(node)
            node_ids.add(node["id"])

    def add_edge(source: str, target: str, etype: str, **extra: Any) -> None:
        edge = {"source": source, "target": target, "type": etype}
        edge.update(extra)
        edges.append(edge)

    for r in extract["results"]:
        path = r["path"]
        fid = f"file:{path}"
        fmeta = FILE_META.get(path, {
            "summary": f"Mã Python module {path}.",
            "complexity": "simple",
            "tags": ["python", "module", "kortek"],
            "languageNotes": "",
        })
        add_node(make_node(fid, "file", path.split("/")[-1], path, fmeta))

        exports = {e["name"] for e in r.get("exports", [])}

        for fn in r.get("functions", []):
            if not is_significant_function(fn, exports):
                continue
            nid = f"function:{path}:{fn['name']}"
            meta = SYMBOL_META.get(nid, {
                "summary": f"Hàm {fn['name']} trong {path}.",
                "complexity": "simple",
                "tags": ["function", "python"],
            })
            add_node(
                make_node(
                    nid,
                    "function",
                    fn["name"],
                    path,
                    meta,
                    fn["startLine"],
                    fn["endLine"],
                )
            )
            add_edge(fid, nid, "contains")
            if fn["name"] in exports:
                add_edge(fid, nid, "exports")

        for cls in r.get("classes", []):
            if not is_significant_class(cls, exports):
                continue
            cid = f"class:{path}:{cls['name']}"
            meta = SYMBOL_META.get(cid, {
                "summary": f"Class {cls['name']} trong {path}.",
                "complexity": "moderate",
                "tags": ["class", "python"],
            })
            add_node(
                make_node(
                    cid,
                    "class",
                    cls["name"],
                    path,
                    meta,
                    cls["startLine"],
                    cls["endLine"],
                )
            )
            add_edge(fid, cid, "contains")
            if cls["name"] in exports:
                add_edge(fid, cid, "exports")

    # Imports — one edge per batchImportData entry
    import_count = 0
    for src_path, targets in batch_import.items():
        src_id = f"file:{src_path}"
        for tgt_path in targets:
            tgt_id = f"file:{tgt_path}"
            add_edge(src_id, tgt_id, "imports")
            import_count += 1

    # Call edges (in-batch callees only)
    skip_callees = {
        "dict", "list", "set", "str", "int", "len", "sorted", "min", "max",
        "print", "open", "range", "enumerate", "zip", "isinstance", "getattr",
        "hasattr", "super", "type", "any", "all", "tuple", "float", "bool",
        "time", "threading", "asyncio", "Path", "logger", "Exception",
    }

    for r in extract["results"]:
        path = r["path"]
        for cg in r.get("callGraph") or []:
            caller = cg["caller"]
            callee_norm = normalize_callee(cg["callee"])
            if not callee_norm or callee_norm in skip_callees:
                continue
            if callee_norm.endswith("strip") or callee_norm in ("append", "get", "items", "keys", "values", "update", "pop", "extend"):
                continue

            src = method_to_class.get((path, caller))
            if not src:
                src = fn_by_path_name.get((path, caller))
            if not src:
                continue

            tgt = fn_by_path_name.get((path, callee_norm))
            if not tgt:
                tgt = global_fn_names.get(callee_norm)
            if not tgt:
                tgt = cls_by_path_name.get((path, callee_norm))
            if not tgt or tgt == src:
                continue
            add_edge(
                src,
                tgt,
                "calls",
                lineNumber=cg.get("lineNumber"),
            )

    out = {"nodes": nodes, "edges": edges}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    calls = sum(1 for e in edges if e["type"] == "calls")
    print(
        json.dumps(
            {
                "nodes": len(nodes),
                "edges": len(edges),
                "imports": import_count,
                "imports_expected": sum(len(v) for v in batch_import.values()),
                "calls_edges": calls,
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
