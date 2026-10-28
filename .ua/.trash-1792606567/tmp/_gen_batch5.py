# -*- coding: utf-8 -*-
"""Generate batch-5.json for Understand-Anything file-analyzer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

UA = Path(r"d:\Prj\kortek\.ua")
EXTRACT_PATH = UA / "tmp" / "ua-file-extract-results-5.json"
INPUT_PATH = UA / "tmp" / "ua-file-analyzer-input-5.json"
BATCHES_PATH = UA / "intermediate" / "batches.json"
OUT_PATH = UA / "intermediate" / "batch-5.json"

# Vietnamese semantic metadata (files + symbols)
META: Dict[str, dict] = {
    "infrastructure/storage/snapshot_fs.py": {
        "file": {
            "summary": "Lưu snapshot JPEG cặp camera khi dispatch thành công: pull frame từ FrameProvider, overlay, ghi filesystem và index metadata tùy chọn.",
            "tags": ["storage", "snapshot", "filesystem", "opencv", "service"],
            "complexity": "complex",
            "languageNotes": "Thread-safe với Lock; tích hợp CUDA event sync khi chốt frame GPU.",
        },
        "_sanitize_for_filename": {
            "summary": "Chuẩn hóa chuỗi thành segment tên file an toàn trên Windows.",
            "tags": ["utility", "sanitization", "filename"],
            "complexity": "simple",
        },
        "SnapshotFsStore": {
            "summary": "Store snapshot pull-model: capture_pair, save_pair_snapshots, retention cleanup_old_snapshots.",
            "tags": ["storage", "snapshot", "jpeg", "dispatch"],
            "complexity": "complex",
        },
    },
    "infrastructure/storage/snapshot_indexer.py": {
        "file": {
            "summary": "Ghi metadata snapshot vào Mongo qua asyncio loop; có NullSnapshotIndexer no-op khi không bật index.",
            "tags": ["storage", "mongodb", "indexer", "async"],
            "complexity": "moderate",
        },
        "SnapshotIndexer": {
            "summary": "Bind event loop và record basename snapshot sau khi ghi đĩa.",
            "tags": ["mongodb", "indexer", "async"],
            "complexity": "moderate",
        },
        "NullSnapshotIndexer": {
            "summary": "No-op indexer khi không cấu hình persistence snapshot.",
            "tags": ["null-object", "indexer"],
            "complexity": "simple",
        },
    },
    "infrastructure/vision/__init__.py": {
        "file": {
            "summary": "Barrel package vision: re-export CameraManager và InferenceEngine cho runtime.",
            "tags": ["barrel", "vision", "entry-point"],
            "complexity": "simple",
        },
    },
    "infrastructure/vision/annexb_pipe.py": {
        "file": {
            "summary": "Tách NAL unit H.264 Annex-B từ byte stream RTSP để feed NVDEC.",
            "tags": ["h264", "annex-b", "nal", "utility"],
            "complexity": "simple",
        },
        "pull_aus": {
            "summary": "Yield access unit (AU) từ buffer Annex-B theo start code.",
            "tags": ["h264", "parser", "streaming"],
            "complexity": "simple",
        },
    },
    "infrastructure/vision/camera_manager.py": {
        "file": {
            "summary": "Orchestrator camera: map node↔camera, start/stop thread CameraProcessor, preview JPEG/meta, capture_for_node cho dispatch.",
            "tags": ["camera", "orchestration", "rtsp", "threading", "service"],
            "complexity": "complex",
            "languageNotes": "Điều phối InferenceEngine, PreviewStore và cấu hình zone enable.",
        },
        "CameraManager": {
            "summary": "Quản lý vòng đời processor từng camera và API preview/capture theo node.",
            "tags": ["camera", "manager", "runtime"],
            "complexity": "complex",
        },
    },
    "infrastructure/vision/camera_processor.py": {
        "file": {
            "summary": "Luồng xử lý một camera: GPUVideoDecoder, ROI detection async, đẩy frame vào InferenceEngine và preview.",
            "tags": ["camera", "pipeline", "gpu", "detection"],
            "complexity": "complex",
        },
        "CameraProcessor": {
            "summary": "Thread loop decode → ROI → inference queue; publish preview khi có watcher.",
            "tags": ["camera", "processor", "gpu"],
            "complexity": "complex",
        },
    },
    "infrastructure/vision/cuda_decode_pool.py": {
        "file": {
            "summary": "Pool CUDA stream decode theo camera index từ settings, tránh tranh chấp NVDEC.",
            "tags": ["cuda", "nvdec", "pool", "utility"],
            "complexity": "simple",
        },
        "get_decode_stream": {
            "summary": "Trả về torch.cuda.Stream cho index camera (round-robin / modulo).",
            "tags": ["cuda", "stream", "decode"],
            "complexity": "simple",
        },
    },
    "infrastructure/vision/detection.py": {
        "file": {
            "summary": "Kiểm tra object trong ROI batch trên tensor CUDA từ kết quả YOLO.",
            "tags": ["detection", "roi", "cuda", "yolo"],
            "complexity": "moderate",
        },
        "has_object_in_rois_batch": {
            "summary": "Vector hóa overlap detection giữa bbox và danh sách ROI.",
            "tags": ["detection", "roi", "batch"],
            "complexity": "moderate",
        },
    },
    "infrastructure/vision/frame_queue.py": {
        "file": {
            "summary": "Hàng đợi frame pre-allocated tensor tránh alloc GPU trong hot path inference.",
            "tags": ["queue", "gpu", "inference", "performance"],
            "complexity": "moderate",
        },
        "PreAllocatedFrameQueue": {
            "summary": "Queue cố định kích thước với put_nowait/get và drop policy.",
            "tags": ["queue", "tensor", "inference"],
            "complexity": "moderate",
        },
    },
    "infrastructure/vision/gpu_frame.py": {
        "file": {
            "summary": "Chuyển decoded frame NVDEC (NV12) sang RGB CHW tensor trên GPU.",
            "tags": ["gpu", "nv12", "color-conversion", "utility"],
            "complexity": "moderate",
        },
        "decoded_frame_to_rgb": {
            "summary": "Entry point chuyển PyNvCodec frame sang tensor RGB cho pipeline vision.",
            "tags": ["gpu", "rgb", "decode"],
            "complexity": "moderate",
        },
    },
    "infrastructure/vision/gpu_video_decoder.py": {
        "file": {
            "summary": "Wrapper NVDEC/PyNvCodec: decode loop RTSP Annex-B, API read() tương thích OpenCV.",
            "tags": ["nvdec", "gpu", "rtsp", "decoder"],
            "complexity": "complex",
        },
        "GPUVideoDecoder": {
            "summary": "Thread decode loop, submit AU, expose width/height và release tài nguyên.",
            "tags": ["nvdec", "decoder", "threading"],
            "complexity": "complex",
        },
    },
    "infrastructure/vision/inference_engine.py": {
        "file": {
            "summary": "Engine inference TensorRT YOLO: batching, multi-slot async, pause/resume, phân phối kết quả theo camera.",
            "tags": ["tensorrt", "yolo", "inference", "gpu", "service"],
            "complexity": "complex",
            "languageNotes": "PreAllocatedFrameQueue + TrtYoloEngine; slot busy tracking.",
        },
        "InferenceEngine": {
            "summary": "Vòng run() poll batch, infer async, distribute detections về camera callbacks.",
            "tags": ["inference", "tensorrt", "batching"],
            "complexity": "complex",
        },
    },
    "infrastructure/vision/preview_draw.py": {
        "file": {
            "summary": "Vẽ overlay bbox/ROI và encode JPEG preview từ frame GPU hoặc numpy.",
            "tags": ["preview", "jpeg", "opencv", "visualization"],
            "complexity": "moderate",
        },
        "draw_overlay": {
            "summary": "Vẽ detection và ROI lên frame BGR cho snapshot/preview.",
            "tags": ["overlay", "visualization", "opencv"],
            "complexity": "moderate",
        },
        "frame_to_bgr": {
            "summary": "Chuyển frame tensor hoặc array sang BGR uint8 cho OpenCV.",
            "tags": ["color-conversion", "opencv", "utility"],
            "complexity": "simple",
        },
    },
    "infrastructure/vision/preview_store.py": {
        "file": {
            "summary": "Lưu JPEG preview mới nhất và meta; hỗ trợ watch flag và get_wait cho HTTP long-poll.",
            "tags": ["preview", "jpeg", "store", "webrtc"],
            "complexity": "moderate",
        },
        "PreviewStore": {
            "summary": "Thread-safe store preview theo camera với Event notify watcher.",
            "tags": ["preview", "store", "threading"],
            "complexity": "moderate",
        },
    },
    "infrastructure/vision/trt_yolo_engine.py": {
        "file": {
            "summary": "Load TensorRT engine YOLO, copy batch GPU, infer async và NMS trên CUDA stream.",
            "tags": ["tensorrt", "yolo", "gpu", "inference"],
            "complexity": "complex",
        },
        "TrtYoloEngine": {
            "summary": "Facade TensorRT với shared engine bytes và TrtExecSlot pool.",
            "tags": ["tensorrt", "yolo", "engine"],
            "complexity": "complex",
        },
        "TrtExecSlot": {
            "summary": "Một execution context + buffers cho batch infer và post-NMS.",
            "tags": ["tensorrt", "slot", "cuda"],
            "complexity": "moderate",
        },
    },
    "infrastructure/webrtc/__init__.py": {
        "file": {
            "summary": "Barrel WebRTC/MediaMTX: export gateway và runner cho app lifespan.",
            "tags": ["barrel", "webrtc", "mediamtx"],
            "complexity": "simple",
        },
    },
    "infrastructure/webrtc/mediamtx_gateway.py": {
        "file": {
            "summary": "Client HTTP WHEP tới MediaMTX: offer SDP, hangup, ICE servers; có NullWebrtcGateway stub.",
            "tags": ["webrtc", "whep", "mediamtx", "gateway"],
            "complexity": "moderate",
        },
        "MediaMtxGateway": {
            "summary": "Đảm bảo path RTSP, proxy WHEP offer/hangup tới MediaMTX API.",
            "tags": ["webrtc", "gateway", "whep"],
            "complexity": "moderate",
        },
        "NullWebrtcGateway": {
            "summary": "Stub gateway khi WebRTC/MediaMTX tắt trong môi trường dev.",
            "tags": ["null-object", "webrtc"],
            "complexity": "simple",
        },
    },
    "infrastructure/webrtc/mediamtx_runner.py": {
        "file": {
            "summary": "Spawn và watchdog process MediaMTX binary; expose status cho health check.",
            "tags": ["mediamtx", "subprocess", "webrtc", "infrastructure"],
            "complexity": "moderate",
        },
        "MediaMtxRunner": {
            "summary": "Start/stop MediaMTX, probe binary, watchdog loop restart khi crash.",
            "tags": ["mediamtx", "runner", "process"],
            "complexity": "moderate",
        },
    },
    "scripts/export_engine.py": {
        "file": {
            "summary": "CLI export ONNX và build TensorRT engine YOLO từ settings; inspect engine metadata.",
            "tags": ["script", "tensorrt", "onnx", "yolo"],
            "complexity": "moderate",
        },
        "export_onnx": {
            "summary": "Xuất model Ultralytics sang ONNX theo cấu hình input size.",
            "tags": ["onnx", "export", "yolo"],
            "complexity": "moderate",
        },
        "build_engine": {
            "summary": "Build file .engine TensorRT từ ONNX với workspace/precision settings.",
            "tags": ["tensorrt", "build", "engine"],
            "complexity": "moderate",
        },
        "inspect_engine": {
            "summary": "In thông tin binding/layer của engine TensorRT đã build.",
            "tags": ["tensorrt", "debug", "inspect"],
            "complexity": "simple",
        },
    },
    "scripts/seed_sandbox.py": {
        "file": {
            "summary": "Seed Mongo sandbox: nodes, cameras, ROI docs và priority metadata cho demo dispatch.",
            "tags": ["script", "mongodb", "seed", "sandbox"],
            "complexity": "moderate",
        },
        "build_docs": {
            "summary": "Tạo danh sách document Mongo từ template node/camera/ROI.",
            "tags": ["seed", "mongodb", "builder"],
            "complexity": "moderate",
        },
        "main": {
            "summary": "Entry CLI: kết nối DB, upsert sandbox collections.",
            "tags": ["cli", "seed", "entry-point"],
            "complexity": "moderate",
        },
    },
    "utils/overlap_utils.py": {
        "file": {
            "summary": "Tính coverage bbox trong ROI (multi-ROI) phục vụ logic detection.",
            "tags": ["geometry", "roi", "utility"],
            "complexity": "moderate",
        },
        "calculate_coverage_multi_rois": {
            "summary": "Tính tỉ lệ overlap giữa một bbox và nhiều polygon ROI.",
            "tags": ["overlap", "roi", "geometry"],
            "complexity": "moderate",
        },
    },
    "utils/rtsp_url.py": {
        "file": {
            "summary": "Encode user/password trong URL RTSP an toàn cho ffmpeg/PyNvCodec.",
            "tags": ["rtsp", "url", "utility"],
            "complexity": "simple",
        },
        "encode_rtsp_userinfo": {
            "summary": "Percent-encode credentials và ghép lại URL RTSP.",
            "tags": ["rtsp", "encoding", "security"],
            "complexity": "simple",
        },
    },
    "utils/setup_log.py": {
        "file": {
            "summary": "Factory logger RotatingFileHandler thống nhất cho toàn project.",
            "tags": ["logging", "utility", "infrastructure"],
            "complexity": "simple",
        },
        "setup_logger": {
            "summary": "Tạo logger named với file log riêng và level từ env.",
            "tags": ["logging", "factory"],
            "complexity": "simple",
        },
    },
}

# Cross-batch symbol targets for calls (neighborMap + common imports)
EXTERNAL_SYMBOLS: Dict[str, str] = {
    "setup_logger": "function:utils/setup_log.py:setup_logger",
    "Settings": "class:config/settings.py:Settings",
    "settings": "file:config/settings.py",
    "RuntimeService": "class:application/runtime/runtime_service.py:RuntimeService",
    "SandboxCameraManager": "class:infrastructure/sandbox/sandbox_camera_manager.py:SandboxCameraManager",
    "resolve_priority": "function:domain/dispatch/priority.py:resolve_priority",
    "start_meta_from_docs": "function:domain/dispatch/priority.py:start_meta_from_docs",
    "start_sort_key": "function:domain/dispatch/priority.py:start_sort_key",
    "lifespan": "function:app.py:lifespan",
    "create_app": "function:app.py:create_app",
}

BATCH_FILES: Set[str] = set()


def load_batch_neighbor_map() -> dict:
    data = json.loads(BATCHES_PATH.read_text(encoding="utf-8"))
    for batch in data.get("batches") or []:
        if batch.get("batchIndex") == 5:
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
    ne = batch_file.get("nonEmptyLines") or batch_file.get("sizeLines") or 0
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
        "tags": fm.get("tags", ["python", "infrastructure"]),
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
    """Map simple name -> node id (batch-internal, last wins on collision)."""
    index: Dict[str, str] = {}
    for r in results:
        path = r["path"]
        for fn in r.get("functions", []):
            index[fn["name"]] = f"function:{path}:{fn['name']}"
        for cls in r.get("classes", []):
            index[cls["name"]] = f"class:{path}:{cls['name']}"
            for m in cls.get("methods") or []:
                index[m] = f"function:{path}:{m}"  # methods not separate nodes
    index.update(EXTERNAL_SYMBOLS)
    return index


def resolve_callee(
    caller_path: str,
    caller: str,
    callee: str,
    class_methods: Dict[str, Set[str]],
    symbol_index: Dict[str, str],
    neighbor_map: dict,
) -> Optional[str]:
    raw = callee.strip()
    if raw in symbol_index:
        return symbol_index[raw]

    # self.method -> class method on same file (no method node: skip)
    if raw.startswith("self."):
        return None

    # attr.method — take method name if in batch class
    if "." in raw:
        parts = raw.split(".")
        tail = parts[-1]
        if tail in symbol_index:
            return symbol_index[tail]
        # module-level from import e.g. settings.FOO -> file
        head = parts[0]
        if head in symbol_index:
            return symbol_index[head]

    # neighborMap symbols for this file's external refs
    for entry in neighbor_map.get(caller_path, []):
        npath = entry.get("path", "")
        for sym in entry.get("symbols") or []:
            if sym == raw or raw.endswith(f".{sym}"):
                if sym[0].isupper():
                    return f"class:{npath}:{sym}"
                return f"function:{npath}:{sym}"

    return None


def caller_node_id(path: str, caller: str, top_functions: Set[str], classes: Dict[str, dict]) -> Optional[str]:
    if caller in top_functions:
        return f"function:{path}:{caller}"
    for cls_name, cls in classes.items():
        methods = set(cls.get("methods") or [])
        if caller in methods:
            return f"class:{path}:{cls_name}"
    if caller == "<module>":
        return f"file:{path}"
    return f"file:{path}"


def main() -> None:
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    inp = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    neighbor_map = load_batch_neighbor_map()
    batch_import = inp["batchImportData"]
    global BATCH_FILES
    BATCH_FILES = {f["path"] for f in inp["batchFiles"]}

    results = extract["results"]
    nodes: List[dict] = []
    edges: List[dict] = []
    node_ids: Set[str] = set()
    exported_by_path: Dict[str, Set[str]] = {
        r["path"]: {e["name"] for e in r.get("exports", [])} for r in results
    }

    symbol_index = build_symbol_index(results)

    for r in results:
        path = r["path"]
        exported = exported_by_path[path]
        nodes.append(file_node(path, r))
        node_ids.add(f"file:{path}")

        for fn in r.get("functions", []):
            if not is_significant_fn(path, fn, exported):
                continue
            n = fn_node(path, fn)
            nodes.append(n)
            node_ids.add(n["id"])
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
            node_ids.add(n["id"])
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

    # imports — exactly one per batchImportData entry
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

    # calls from callGraph (intra-batch + resolved cross-batch)
    seen_calls: Set[Tuple[str, str]] = set()
    for r in results:
        path = r["path"]
        top_functions = {fn["name"] for fn in r.get("functions", [])}
        classes = {c["name"]: c for c in r.get("classes", [])}
        class_methods = {cn: set(c.get("methods") or []) for cn, c in classes.items()}

        for cg in r.get("callGraph") or []:
            caller = cg.get("caller", "")
            callee = cg.get("callee", "")
            target = resolve_callee(
                path, caller, callee, class_methods, symbol_index, neighbor_map
            )
            if not target:
                continue
            # Skip stdlib / builtin noise
            if target.startswith("function:") and any(
                x in callee for x in ("logger.", "print", "str", "int", "max", "min", "len")
            ):
                if "setup_log" not in target and "setup_logger" not in target:
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
    contains = sum(1 for e in edges if e["type"] == "contains")
    calls = sum(1 for e in edges if e["type"] == "calls")
    print("contains", contains, "calls", calls)


if __name__ == "__main__":
    main()
