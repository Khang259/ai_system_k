# -*- coding: utf-8 -*-
"""Generate batch-6.json for Understand-Anything file-analyzer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

UA = Path(r"d:\Prj\kortek\.ua")
EXTRACT_PATH = UA / "tmp" / "ua-file-extract-results-6.json"
INPUT_PATH = UA / "tmp" / "ua-file-analyzer-input-6.json"
BATCHES_PATH = UA / "intermediate" / "batches.json"
OUT_PATH = UA / "intermediate" / "batch-6.json"

META: Dict[str, dict] = {
    "application/cameras/__init__.py": {
        "file": {
            "summary": "Barrel package cameras: re-export use case start/stop, scan, dispatch, WebRTC và zone cho container/routes.",
            "tags": ["barrel", "use-case", "cameras", "entry-point"],
            "complexity": "simple",
        },
    },
    "application/cameras/cancel_batch.py": {
        "file": {
            "summary": "Use case hủy batch dispatch đang chờ: reset ScanSession và emit smoke trail.",
            "tags": ["use-case", "dispatch", "batch", "cameras"],
            "complexity": "simple",
        },
        "CancelBatch": {
            "summary": "Reset session scan khi operator hủy batch; trả UseCaseResult với node đã dispatch.",
            "tags": ["use-case", "cancel", "batch"],
            "complexity": "simple",
        },
    },
    "application/cameras/confirm_dispatch.py": {
        "file": {
            "summary": "Use case confirm-dispatch: sau khi operator xác nhận hàng đã đẩy, mở batch start isReady và cổng gửi ICS theo priority.",
            "tags": ["use-case", "dispatch", "batch", "ics"],
            "complexity": "moderate",
        },
        "ConfirmDispatch": {
            "summary": "Kiểm tra inference/state, validate dispatchable starts, gọi ScanSession.start và emit audit.",
            "tags": ["use-case", "confirm", "dispatch"],
            "complexity": "moderate",
        },
    },
    "application/cameras/on_dispatch_success.py": {
        "file": {
            "summary": "Hook sau dispatch thành công: cập nhật batch, auto-pause/reset khi batch hoàn tất.",
            "tags": ["use-case", "dispatch", "callback"],
            "complexity": "moderate",
        },
        "OnDispatchSuccess": {
            "summary": "record_success trên ScanSession; should_auto_pause → reset session và smoke emit.",
            "tags": ["use-case", "success", "batch"],
            "complexity": "moderate",
        },
    },
    "application/cameras/pause_scan.py": {
        "file": {
            "summary": "Use case pause inference scan và reset batch session (operator dừng quét).",
            "tags": ["use-case", "scan", "pause", "inference"],
            "complexity": "simple",
        },
        "PauseScan": {
            "summary": "Gọi InferencePort.pause và ScanSession.reset khi runtime sẵn sàng.",
            "tags": ["use-case", "pause", "scan"],
            "complexity": "simple",
        },
    },
    "application/cameras/start_scan.py": {
        "file": {
            "summary": "Use case resume inference sau khi camera đã start; yêu cầu đủ camera streaming.",
            "tags": ["use-case", "scan", "resume", "inference"],
            "complexity": "simple",
        },
        "StartScan": {
            "summary": "Kiểm tra camera/inference ready, resume inference và emit smoke trail.",
            "tags": ["use-case", "start-scan", "runtime"],
            "complexity": "simple",
        },
    },
    "application/cameras/start_stop.py": {
        "file": {
            "summary": "Use case start/stop toàn bộ camera runtime: load model, poll streaming status, pause inference khi stop.",
            "tags": ["use-case", "camera", "runtime", "async"],
            "complexity": "complex",
        },
        "StartAllCameras": {
            "summary": "start_all cameras, chờ streaming ổn định, trả payload status và streaming warnings.",
            "tags": ["use-case", "start", "camera"],
            "complexity": "complex",
        },
        "StopAllCameras": {
            "summary": "stop_all cameras, pause inference và reset scan session.",
            "tags": ["use-case", "stop", "camera"],
            "complexity": "simple",
        },
        "_streaming_warnings": {
            "summary": "Thu thập cảnh báo camera chưa streaming/error từ status dict.",
            "tags": ["utility", "streaming", "validation"],
            "complexity": "simple",
        },
    },
    "application/cameras/webrtc_sessions.py": {
        "file": {
            "summary": "Registry in-memory session WebRTC WHEP: create/set_remote/pop với giới hạn và thread-safe Lock.",
            "tags": ["webrtc", "session", "registry", "threading"],
            "complexity": "moderate",
        },
        "WebrtcSessionRegistry": {
            "summary": "Quản lý map session_id → metadata; drain/clear khi shutdown.",
            "tags": ["webrtc", "registry", "whep"],
            "complexity": "moderate",
        },
    },
    "application/cameras/webrtc_signaling.py": {
        "file": {
            "summary": "Use case WHEP signaling: offer SDP, hangup session, đếm grid WebRTC.",
            "tags": ["use-case", "webrtc", "whep", "signaling"],
            "complexity": "moderate",
        },
        "OfferWebrtc": {
            "summary": "Tạo registry session, proxy whep_offer qua WebrtcRunnerPort, lưu remote SDP.",
            "tags": ["use-case", "webrtc", "offer"],
            "complexity": "moderate",
        },
        "DeleteWebrtcSession": {
            "summary": "Pop session và gọi gateway hangup theo camera id.",
            "tags": ["use-case", "webrtc", "hangup"],
            "complexity": "simple",
        },
        "GetWebrtcGrid": {
            "summary": "Trả số session WebRTC đang active trong registry.",
            "tags": ["use-case", "webrtc", "grid"],
            "complexity": "simple",
        },
    },
    "application/cameras/zone.py": {
        "file": {
            "summary": "Use case bật/tắt camera theo zone (enable/disable) và reset scan khi stop zone.",
            "tags": ["use-case", "zone", "camera"],
            "complexity": "simple",
        },
        "StartZoneCameras": {
            "summary": "set_zone_enabled(True) và trả status sau khi kiểm tra runtime ready.",
            "tags": ["use-case", "zone", "start"],
            "complexity": "simple",
        },
        "StopZoneCameras": {
            "summary": "Tắt zone, pause inference nếu cần và reset ScanSession.",
            "tags": ["use-case", "zone", "stop"],
            "complexity": "simple",
        },
    },
    "application/dispatch/dispatch_gate.py": {
        "file": {
            "summary": "Cổng lọc cặp dispatch trước ICS: chỉ khi batch active, strict zone head order, phát hiện node mới.",
            "tags": ["dispatch", "gate", "batch", "zone-order"],
            "complexity": "complex",
            "languageNotes": "PairManager gọi filter mỗi vòng; không pause inference — chỉ chặn gửi lệnh.",
        },
        "DispatchGate": {
            "summary": "filter() áp dụng allowed_pairs, busy_zones, find_new_nodes và reset batch khi có start mới.",
            "tags": ["dispatch", "gate", "filter"],
            "complexity": "complex",
        },
    },
    "application/scan_session.py": {
        "file": {
            "summary": "State in-memory batch dispatch (ScanSession): thread-safe BatchSnapshot, stop reason cho FE.",
            "tags": ["application-state", "batch", "dispatch", "threading"],
            "complexity": "moderate",
        },
        "ScanSession": {
            "summary": "reset/start/record_success/get/status bọc domain batch_policy với Lock.",
            "tags": ["session", "batch", "state"],
            "complexity": "moderate",
        },
    },
    "domain/batch_policy.py": {
        "file": {
            "summary": "Domain policy batch dispatch: BatchSnapshot, zone heads, allowed pairs, auto-pause và idle batch.",
            "tags": ["domain", "batch", "dispatch", "policy"],
            "complexity": "complex",
        },
        "BatchSnapshot": {
            "summary": "Immutable snapshot batch: nodes, sum_request, active/dispatched counters.",
            "tags": ["domain", "data-model", "batch"],
            "complexity": "moderate",
        },
        "start_batch": {
            "summary": "Khởi tạo BatchSnapshot từ tập node isReady khi confirm dispatch.",
            "tags": ["domain", "batch", "factory"],
            "complexity": "simple",
        },
        "record_dispatch_success": {
            "summary": "Cập nhật snapshot sau mỗi dispatch thành công (node_id tùy chọn).",
            "tags": ["domain", "batch", "transition"],
            "complexity": "moderate",
        },
        "should_auto_pause": {
            "summary": "True khi batch đã dispatch hết node trong snapshot.",
            "tags": ["domain", "batch", "rule"],
            "complexity": "simple",
        },
        "zone_heads": {
            "summary": "Map zone → start id ưu tiên thấp nhất trong batch theo start_meta.",
            "tags": ["domain", "zone", "priority"],
            "complexity": "moderate",
        },
        "busy_zones": {
            "summary": "Tập zone đang có start bị lock (lệnh ICS đang chạy).",
            "tags": ["domain", "zone", "lock"],
            "complexity": "simple",
        },
        "waiting_for": {
            "summary": "Mô tả zone/start đang chờ vì head khác zone bận.",
            "tags": ["domain", "zone", "diagnostics"],
            "complexity": "moderate",
        },
        "stuck_nodes": {
            "summary": "Node trong batch nhưng start chưa ready — gợi ý vấn đề runtime.",
            "tags": ["domain", "batch", "diagnostics"],
            "complexity": "simple",
        },
        "allowed_pairs": {
            "summary": "Lọc cặp dispatch được phép theo batch, zone head và locked starts.",
            "tags": ["domain", "dispatch", "filter"],
            "complexity": "complex",
        },
        "dispatchable_starts": {
            "summary": "Giao ready_starts với validate_pairs từ PairManager.",
            "tags": ["domain", "dispatch", "validation"],
            "complexity": "simple",
        },
        "find_new_nodes": {
            "summary": "Diff node hiện tại vs snapshot — phát hiện start mới ngoài batch.",
            "tags": ["domain", "batch", "diff"],
            "complexity": "simple",
        },
        "should_pause_for_new_nodes": {
            "summary": "Quy tắc reset batch khi có node mới xuất hiện sau confirm.",
            "tags": ["domain", "batch", "rule"],
            "complexity": "moderate",
        },
        "idle_batch": {
            "summary": "BatchSnapshot rỗng/inactive — trạng thái mặc định ScanSession.",
            "tags": ["domain", "batch", "factory"],
            "complexity": "simple",
        },
        "locked_start_ids": {
            "summary": "Trích start id đang lock từ snapshot ICS/node state.",
            "tags": ["domain", "lock", "ics"],
            "complexity": "moderate",
        },
    },
    "infrastructure/sandbox/smoke_trail.py": {
        "file": {
            "summary": "Smoke trail JSON log cho sandbox/demo: emit action, node runtime view, inference paused probe.",
            "tags": ["sandbox", "logging", "observability", "debug"],
            "complexity": "moderate",
        },
        "emit": {
            "summary": "Ghi structured log khi bật smoke trail trong settings.",
            "tags": ["sandbox", "audit", "logging"],
            "complexity": "simple",
        },
        "node_runtime_view": {
            "summary": "Chuyển NodeStateStore snapshot thành dict gọn cho smoke/FE debug.",
            "tags": ["sandbox", "mapper", "runtime"],
            "complexity": "moderate",
        },
        "inference_paused": {
            "summary": "Suy luận trạng thái pause từ InferencePort (is_paused hoặc Event).",
            "tags": ["sandbox", "inference", "utility"],
            "complexity": "simple",
        },
    },
}

EXTERNAL_SYMBOLS: Dict[str, str] = {
    "UseCaseResult": "class:application/result.py:UseCaseResult",
    "setup_logger": "function:utils/setup_log.py:setup_logger",
    "start_sort_key": "function:domain/dispatch/priority.py:start_sort_key",
    "start_meta_from_docs": "function:domain/dispatch/priority.py:start_meta_from_docs",
    "resolve_priority": "function:domain/dispatch/priority.py:resolve_priority",
    "Settings": "class:config/settings.py:Settings",
    "BatchSnapshot": "class:domain/batch_policy.py:BatchSnapshot",
    "idle_batch": "function:domain/batch_policy.py:idle_batch",
    "start_batch": "function:domain/batch_policy.py:start_batch",
    "record_dispatch_success": "function:domain/batch_policy.py:record_dispatch_success",
    "should_auto_pause": "function:domain/batch_policy.py:should_auto_pause",
    "dispatchable_starts": "function:domain/batch_policy.py:dispatchable_starts",
    "allowed_pairs": "function:domain/batch_policy.py:allowed_pairs",
    "busy_zones": "function:domain/batch_policy.py:busy_zones",
    "find_new_nodes": "function:domain/batch_policy.py:find_new_nodes",
    "zone_heads": "function:domain/batch_policy.py:zone_heads",
    "_zone_of": "function:domain/batch_policy.py:_zone_of",
    "emit": "function:infrastructure/sandbox/smoke_trail.py:emit",
    "_enabled": "function:infrastructure/sandbox/smoke_trail.py:_enabled",
}


def load_batch_neighbor_map() -> dict:
    data = json.loads(BATCHES_PATH.read_text(encoding="utf-8"))
    for batch in data.get("batches") or []:
        if batch.get("batchIndex") == 6:
            return batch.get("neighborMap") or {}
    return {}


def is_significant_fn(path: str, fn: dict, exported: Set[str]) -> bool:
    lines = fn["endLine"] - fn["startLine"] + 1
    return lines >= 10 or fn["name"] in exported


def is_significant_cls(path: str, cls: dict, exported: Set[str]) -> bool:
    lines = cls["endLine"] - cls["startLine"] + 1
    methods = cls.get("methods") or []
    return len(methods) >= 2 or lines >= 20 or cls["name"] in exported


def sym_meta(path: str, name: str, default_complexity: str = "moderate") -> dict:
    file_meta = META.get(path, {})
    if name in file_meta:
        return file_meta[name]
    return {
        "summary": f"Thành phần {name} trong {path}.",
        "tags": ["utility"],
        "complexity": default_complexity,
    }


def file_node(path: str, batch_file: dict) -> dict:
    fm = META.get(path, {}).get("file", {})
    name = path.split("/")[-1]
    ne = batch_file.get("nonEmptyLines") or batch_file.get("totalLines") or 0
    complexity = fm.get("complexity")
    if not complexity:
        if ne > 200:
            complexity = "complex"
        elif ne > 50:
            complexity = "moderate"
        else:
            complexity = "simple"
    node: dict = {
        "id": f"file:{path}",
        "type": "file",
        "name": name,
        "filePath": path,
        "summary": fm.get("summary", f"Mã nguồn Python: {path}."),
        "tags": fm.get("tags", ["python", "application"]),
        "complexity": complexity,
    }
    if fm.get("languageNotes"):
        node["languageNotes"] = fm["languageNotes"]
    return node


def fn_node(path: str, fn: dict) -> dict:
    sm = sym_meta(path, fn["name"])
    return {
        "id": f"function:{path}:{fn['name']}",
        "type": "function",
        "name": fn["name"],
        "filePath": path,
        "lineRange": [fn["startLine"], fn["endLine"]],
        "summary": sm["summary"],
        "tags": sm["tags"],
        "complexity": sm.get("complexity", "simple"),
    }


def cls_node(path: str, cls: dict) -> dict:
    sm = sym_meta(path, cls["name"])
    return {
        "id": f"class:{path}:{cls['name']}",
        "type": "class",
        "name": cls["name"],
        "filePath": path,
        "lineRange": [cls["startLine"], cls["endLine"]],
        "summary": sm["summary"],
        "tags": sm["tags"],
        "complexity": sm.get("complexity", "moderate"),
    }


def build_symbol_index(results: List[dict]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for r in results:
        path = r["path"]
        for fn in r.get("functions", []):
            index[fn["name"]] = f"function:{path}:{fn['name']}"
        for cls in r.get("classes", []):
            index[cls["name"]] = f"class:{path}:{cls['name']}"
    index.update(EXTERNAL_SYMBOLS)
    return index


def resolve_callee(
    caller_path: str,
    caller: str,
    callee: str,
    symbol_index: Dict[str, str],
    neighbor_map: dict,
) -> Optional[str]:
    raw = callee.strip()
    if raw in symbol_index:
        return symbol_index[raw]

    if raw.startswith("self."):
        return None

    if "." in raw:
        parts = raw.split(".")
        tail = parts[-1]
        if tail in symbol_index:
            return symbol_index[tail]
        head = parts[0]
        if head in symbol_index:
            return symbol_index[head]

    for entry in neighbor_map.get(caller_path, []):
        npath = entry.get("path", "")
        for sym in entry.get("symbols") or []:
            if sym == raw or raw.endswith(f".{sym}"):
                if sym[0].isupper():
                    return f"class:{npath}:{sym}"
                return f"function:{npath}:{sym}"

    return None


def caller_node_id(
    path: str, caller: str, top_functions: Set[str], classes: Dict[str, dict]
) -> Optional[str]:
    if caller in top_functions:
        return f"function:{path}:{caller}"
    for cls_name, cls in classes.items():
        methods = set(cls.get("methods") or [])
        if caller in methods:
            return f"class:{path}:{cls_name}"
    if caller == "<module>":
        return f"file:{path}"
    return f"file:{path}"


def skip_noise_callee(callee: str, target: str) -> bool:
    noise = (
        "logger.",
        "print",
        "sorted",
        "list",
        "set",
        "frozenset",
        "str",
        "int",
        "max",
        "min",
        "len",
        "bool",
        "hasattr",
        "getattr",
        "asyncio.",
        "time.",
        "threading.",
        "uuid.",
        "json.",
        "datetime.",
        "warnings.",
    )
    if any(x in callee for x in noise):
        if "setup_log" not in target and "setup_logger" not in target:
            return True
    return False


def main() -> None:
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    inp = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    neighbor_map = load_batch_neighbor_map()
    batch_import = inp["batchImportData"]

    results = extract["results"]
    nodes: List[dict] = []
    edges: List[dict] = []
    exported_by_path: Dict[str, Set[str]] = {
        r["path"]: {e["name"] for e in r.get("exports", [])} for r in results
    }

    symbol_index = build_symbol_index(results)

    for r in results:
        path = r["path"]
        exported = exported_by_path[path]
        nodes.append(file_node(path, r))

        for fn in r.get("functions", []):
            if not is_significant_fn(path, fn, exported):
                continue
            n = fn_node(path, fn)
            nodes.append(n)
            edges.append(
                {
                    "source": f"file:{path}",
                    "target": n["id"],
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1.0,
                }
            )
            if fn["name"] in exported:
                edges.append(
                    {
                        "source": f"file:{path}",
                        "target": n["id"],
                        "type": "exports",
                        "direction": "forward",
                        "weight": 0.8,
                    }
                )

        for cls in r.get("classes", []):
            if not is_significant_cls(path, cls, exported):
                continue
            n = cls_node(path, cls)
            nodes.append(n)
            edges.append(
                {
                    "source": f"file:{path}",
                    "target": n["id"],
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1.0,
                }
            )
            if cls["name"] in exported:
                edges.append(
                    {
                        "source": f"file:{path}",
                        "target": n["id"],
                        "type": "exports",
                        "direction": "forward",
                        "weight": 0.8,
                    }
                )

    import_count = 0
    for src, targets in batch_import.items():
        for tgt in targets:
            edges.append(
                {
                    "source": f"file:{src}",
                    "target": f"file:{tgt}",
                    "type": "imports",
                    "direction": "forward",
                    "weight": 0.7,
                }
            )
            import_count += 1

    seen_calls: Set[Tuple[str, str]] = set()
    for r in results:
        path = r["path"]
        top_functions = {fn["name"] for fn in r.get("functions", [])}
        classes = {c["name"]: c for c in r.get("classes", [])}

        for cg in r.get("callGraph") or []:
            caller = cg.get("caller", "")
            callee = cg.get("callee", "")
            target = resolve_callee(path, caller, callee, symbol_index, neighbor_map)
            if not target:
                continue
            if skip_noise_callee(callee, target):
                continue
            src = caller_node_id(path, caller, top_functions, classes)
            if not src:
                continue
            key = (src, target)
            if key in seen_calls:
                continue
            seen_calls.add(key)
            edges.append(
                {
                    "source": src,
                    "target": target,
                    "type": "calls",
                    "direction": "forward",
                    "weight": 0.8,
                }
            )

    out = {"nodes": nodes, "edges": edges}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    expected_imports = sum(len(v) for v in batch_import.values())
    print("nodes", len(nodes))
    print("edges", len(edges))
    print("imports", import_count, "expected", expected_imports)


if __name__ == "__main__":
    main()
