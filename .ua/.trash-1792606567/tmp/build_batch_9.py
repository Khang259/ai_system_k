# -*- coding: utf-8 -*-
"""Generate batch-9.json GraphFragment for Understand-Anything."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

UA = Path(r"d:\Prj\kortek\.ua")
EXTRACT_PATH = UA / "tmp" / "ua-file-extract-results-9.json"
INPUT_PATH = UA / "tmp" / "ua-file-analyzer-input-9.json"
BATCHES_PATH = UA / "intermediate" / "batches.json"
OUT_PATH = UA / "intermediate" / "batch-9.json"
BATCH_INDEX = 9

SKIPPED_PATHS = {
    ".github/CODEOWNERS",
    ".python-version",
    "infrastructure/storage/.gitkeep",
    "infrastructure/vision/.gitkeep",
}

META: Dict[str, dict] = {
    ".github/CODEOWNERS": {
        "file": {
            "summary": "Quy tắc GitHub CODEOWNERS: gán reviewer theo đường dẫn (vision, dispatch, presentation, …).",
            "tags": ["github", "codeowners", "governance", "review"],
            "complexity": "simple",
        },
    },
    ".python-version": {
        "file": {
            "summary": "Pin phiên bản Python runtime (pyenv/asdf): 3.10 cho dự án.",
            "tags": ["python", "toolchain", "config", "version-pin"],
            "complexity": "simple",
        },
    },
    "application/__init__.py": {
        "file": {
            "summary": "Docstring package application: use case + ports, không phụ thuộc Mongo/torch/requests.",
            "tags": ["barrel", "application", "layer", "entry-point"],
            "complexity": "simple",
            "languageNotes": "Package marker clean architecture.",
        },
    },
    "application/dispatch/__init__.py": {
        "file": {
            "summary": "Package marker subpackage dispatch (barrel rỗng).",
            "tags": ["barrel", "dispatch", "package"],
            "complexity": "simple",
        },
    },
    "application/state/__init__.py": {
        "file": {
            "summary": "Package marker subpackage state (barrel rỗng).",
            "tags": ["barrel", "state", "package"],
            "complexity": "simple",
        },
    },
    "config/__init__.py": {
        "file": {
            "summary": "Package marker config (barrel rỗng).",
            "tags": ["barrel", "config", "package"],
            "complexity": "simple",
        },
    },
    "config/mediamtx.yml": {
        "file": {
            "summary": "Cấu hình MediaMTX: WebRTC :8890, API :9997, RTSP passthrough không transcode, paths rỗng.",
            "tags": ["mediamtx", "webrtc", "yaml", "config", "streaming"],
            "complexity": "simple",
            "languageNotes": "Được mediamtx_runner đọc khi khởi chạy sidecar.",
        },
    },
    "domain/__init__.py": {
        "file": {
            "summary": "Package marker tầng domain (barrel rỗng).",
            "tags": ["barrel", "domain", "layer"],
            "complexity": "simple",
        },
    },
    "infrastructure/__init__.py": {
        "file": {
            "summary": "Package marker tầng infrastructure (barrel rỗng).",
            "tags": ["barrel", "infrastructure", "layer"],
            "complexity": "simple",
        },
    },
    "infrastructure/storage/.gitkeep": {
        "file": {
            "summary": "Giữ thư mục storage trong git khi chưa có artifact snapshot.",
            "tags": ["gitkeep", "storage", "placeholder"],
            "complexity": "simple",
        },
    },
    "infrastructure/vision/.gitkeep": {
        "file": {
            "summary": "Giữ thư mục vision trong git trước khi có model/binary GPU.",
            "tags": ["gitkeep", "vision", "placeholder"],
            "complexity": "simple",
        },
    },
    "presentation/__init__.py": {
        "file": {
            "summary": "Package marker tầng presentation / FastAPI (barrel rỗng).",
            "tags": ["barrel", "presentation", "layer"],
            "complexity": "simple",
        },
    },
    "presentation/routes/__init__.py": {
        "file": {
            "summary": "Package marker routes (barrel rỗng).",
            "tags": ["barrel", "routes", "api"],
            "complexity": "simple",
        },
    },
    "utils/__init__.py": {
        "file": {
            "summary": "Package marker utils dùng chung (barrel rỗng).",
            "tags": ["barrel", "utils", "package"],
            "complexity": "simple",
        },
    },
    "scripts/cleanup_orphan_rois.py": {
        "file": {
            "summary": "CLI Mongo: xóa ROI trên mọi camera trừ cameraId 1 và 2 để tránh ghi đè node_id.",
            "tags": ["script", "mongodb", "migration", "roi", "maintenance"],
            "complexity": "moderate",
        },
        "main": {
            "summary": "Parse args, kết nối Mongo, liệt kê và clear rois (hoặc dry-run).",
            "tags": ["cli", "mongodb", "maintenance"],
            "complexity": "moderate",
        },
    },
    "scripts/migrate_ssot_nodes_pairs.py": {
        "file": {
            "summary": "Migration SSOT: dọn orphan nodes, sync zone_id node từ camera, unset pairs.zone_id.",
            "tags": ["script", "mongodb", "migration", "ssot", "nodes"],
            "complexity": "complex",
        },
        "_cam_ids": {
            "summary": "Thu thập tập camera_id hợp lệ từ collection cameras.",
            "tags": ["mongodb", "utility"],
            "complexity": "simple",
        },
        "_delete_pairs_for_node": {
            "summary": "Xóa mọi pair document tham chiếu node_id (dry-run tùy chọn).",
            "tags": ["mongodb", "pairs", "cleanup"],
            "complexity": "simple",
        },
        "_unset_roi_keys": {
            "summary": "Gỡ key ROI trên mọi camera gắn node_id trước khi xóa node.",
            "tags": ["mongodb", "roi", "cleanup"],
            "complexity": "simple",
        },
        "migrate_orphans": {
            "summary": "Tìm node mồ côi (camera_id null/không tồn tại) và xóa pairs/ROI/node.",
            "tags": ["migration", "orphan", "nodes"],
            "complexity": "moderate",
        },
        "sync_node_zones": {
            "summary": "Đồng bộ nodes.zone_id theo cameras.zone_id cho từng camera_id.",
            "tags": ["migration", "zone", "sync"],
            "complexity": "moderate",
        },
        "unset_pair_zones": {
            "summary": "Unset field zone_id trên toàn bộ collection pairs.",
            "tags": ["migration", "pairs", "schema"],
            "complexity": "simple",
        },
        "main": {
            "summary": "Orchestrate migrate_orphans → sync_node_zones → unset_pair_zones với --dry-run.",
            "tags": ["cli", "orchestration"],
            "complexity": "simple",
        },
    },
    "scripts/migrate_start_priority_per_zone.py": {
        "file": {
            "summary": "Gán start_priority tuần tự trong từng zone_id và tạo index compound trên nodes.",
            "tags": ["script", "mongodb", "migration", "priority", "zones"],
            "complexity": "moderate",
        },
        "_digits_key": {
            "summary": "Sort key số từ node_id (chỉ giữ chữ số) cho thứ tự trong zone.",
            "tags": ["utility", "sorting"],
            "complexity": "simple",
        },
        "migrate": {
            "summary": "Nhóm node theo zone, sort và gán start_priority 0..n-1.",
            "tags": ["migration", "priority"],
            "complexity": "moderate",
        },
        "ensure_index": {
            "summary": "Tạo index (zone_id, start_priority) trên collection nodes nếu chưa có.",
            "tags": ["mongodb", "index"],
            "complexity": "simple",
        },
        "main": {
            "summary": "CLI kết nối Mongo, chạy migrate và ensure_index.",
            "tags": ["cli", "orchestration"],
            "complexity": "simple",
        },
    },
    "scripts/seed_db.py": {
        "file": {
            "summary": "Seed mock cameras vào Mongo cho stress test: RTSP URL Hikvision, zone AE5.",
            "tags": ["script", "mongodb", "seed", "mock-data", "cameras"],
            "complexity": "moderate",
        },
        "make_rtsp_url": {
            "summary": "Build URL RTSP sub-stream channel 102 từ IP và credential cấu hình.",
            "tags": ["rtsp", "utility", "hikvision"],
            "complexity": "simple",
        },
        "generate_camera_docs": {
            "summary": "Sinh danh sách document camera MOCK-CAM-* với IP cố định và metadata zone.",
            "tags": ["mock-data", "generator"],
            "complexity": "moderate",
        },
        "main": {
            "summary": "Xóa collection cameras, insert mock docs và in thống kê mẫu.",
            "tags": ["cli", "seed"],
            "complexity": "moderate",
        },
    },
}


def load_neighbor_map() -> dict:
    batches = json.loads(BATCHES_PATH.read_text(encoding="utf-8"))
    for b in batches["batches"]:
        if b["batchIndex"] == BATCH_INDEX:
            return b.get("neighborMap") or {}
    return {}


def is_significant_fn(path: str, fn: dict, exported: Set[str]) -> bool:
    if path.startswith("scripts/"):
        lines = fn["endLine"] - fn["startLine"] + 1
        return lines >= 10 or fn["name"] in exported
    lines = fn["endLine"] - fn["startLine"] + 1
    return lines >= 10 or fn["name"] in exported


def sym_meta(path: str, name: str) -> dict:
    file_meta = META.get(path, {})
    if name in file_meta:
        return file_meta[name]
    return {
        "summary": f"Thành phần `{name}` trong `{path}`.",
        "tags": ["utility"],
        "complexity": "simple",
    }


def file_node(path: str, batch_file: Optional[dict], extract_row: Optional[dict]) -> dict:
    fm = META.get(path, {}).get("file", {})
    name = path.split("/")[-1]
    if extract_row:
        ne = extract_row.get("nonEmptyLines") or extract_row.get("totalLines") or 0
    elif batch_file:
        ne = batch_file.get("sizeLines") or 0
    else:
        ne = 0
    complexity = fm.get("complexity")
    if not complexity:
        if ne > 120:
            complexity = "complex"
        elif ne > 40:
            complexity = "moderate"
        else:
            complexity = "simple"
    node: dict = {
        "id": f"file:{path}",
        "type": "file",
        "name": name,
        "filePath": path,
        "summary": fm.get("summary", f"Tệp `{path}`."),
        "tags": (fm.get("tags") or ["utility"])[:5],
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
        "tags": (sm.get("tags") or ["utility"])[:5],
        "complexity": sm.get("complexity", "simple"),
    }


def build_symbol_index(results: List[dict]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for r in results:
        path = r["path"]
        for fn in r.get("functions", []):
            index[fn["name"]] = f"function:{path}:{fn['name']}"
        for cls in r.get("classes", []):
            index[cls["name"]] = f"class:{path}:{cls['name']}"
    return index


def resolve_callee(
    caller_path: str,
    callee: str,
    symbol_index: Dict[str, str],
    neighbor_map: dict,
) -> Optional[str]:
    raw = callee.strip()
    base = raw.split("(")[0].strip()
    if base in symbol_index:
        return symbol_index[base]
    if "." in raw:
        tail = raw.split(".")[-1]
        if tail in symbol_index:
            return symbol_index[tail]
    for entry in neighbor_map.get(caller_path, []):
        npath = entry.get("path", "")
        for sym in entry.get("symbols") or []:
            if sym == base or raw.endswith(f".{sym}"):
                if sym[0].isupper():
                    return f"class:{npath}:{sym}"
                return f"function:{npath}:{sym}"
    return None


def caller_node_id(path: str, caller: str, top_functions: Set[str]) -> Optional[str]:
    if caller in top_functions:
        return f"function:{path}:{caller}"
    return None


def main() -> None:
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    inp = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    neighbor_map = load_neighbor_map()
    batch_import = inp["batchImportData"]
    batch_files_by_path = {f["path"]: f for f in inp["batchFiles"]}
    extract_by_path = {r["path"]: r for r in extract["results"]}

    nodes: List[dict] = []
    edges: List[dict] = []
    node_ids: Set[str] = set()

    # All file nodes (18 paths from input)
    for path in [f["path"] for f in inp["batchFiles"]]:
        nodes.append(
            file_node(path, batch_files_by_path.get(path), extract_by_path.get(path))
        )
        node_ids.add(f"file:{path}")

    symbol_index = build_symbol_index(extract["results"])

    for r in extract["results"]:
        path = r["path"]
        exported = {e["name"] for e in r.get("exports", [])}
        fid = f"file:{path}"

        for fn in r.get("functions", []):
            if not is_significant_fn(path, fn, exported):
                continue
            n = fn_node(path, fn)
            nodes.append(n)
            node_ids.add(n["id"])
            edges.append(
                {
                    "source": fid,
                    "target": n["id"],
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1.0,
                }
            )
            if fn["name"] in exported:
                edges.append(
                    {
                        "source": fid,
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
    noise_callees = ("print", "len", "int", "str", "sorted", "list", "set", "enumerate", "defaultdict")

    for r in extract["results"]:
        path = r["path"]
        top_functions = {fn["name"] for fn in r.get("functions", [])}
        for cg in r.get("callGraph") or []:
            caller = cg.get("caller", "")
            callee = cg.get("callee", "")
            if any(callee.startswith(n) or callee.split("(")[0].strip() == n for n in noise_callees):
                continue
            target = resolve_callee(path, callee, symbol_index, neighbor_map)
            if not target or target not in node_ids:
                continue
            src = caller_node_id(path, caller, top_functions)
            if not src or src not in node_ids:
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

    out: dict[str, Any] = {"nodes": nodes, "edges": edges}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    expected_imports = sum(len(v) for v in batch_import.values())
    assert import_count == expected_imports
    print(
        json.dumps(
            {
                "output": str(OUT_PATH),
                "nodes": len(nodes),
                "edges": len(edges),
                "imports": import_count,
                "files": len(inp["batchFiles"]),
                "skipped_file_nodes": len(SKIPPED_PATHS),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
