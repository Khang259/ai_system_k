# -*- coding: utf-8 -*-
"""Generate batch-8.json — docs/config (README, pyproject, requirements)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(r"d:\Prj\kortek")
EXTRACT_PATH = ROOT / ".ua" / "tmp" / "ua-file-extract-results-8.json"
INPUT_PATH = ROOT / ".ua" / "tmp" / "ua-file-analyzer-input-8.json"
OUT_PATH = ROOT / ".ua" / "intermediate" / "batch-8.json"

ENTRY_APP = "file:app.py"
ENTRY_MAIN = "file:main.py"

FILE_NODES: dict[str, dict[str, Any]] = {
    "README.md": {
        "id": "document:README.md",
        "type": "document",
        "summary": (
            "Tài liệu onboarding AMR Camera Dispatch: yêu cầu GPU/CUDA/TensorRT, "
            "uv sync, `.env`, MongoDB, seed user/camera và chạy FastAPI (`uvicorn app:app`). "
            "Mô tả kiến trúc layered và link runbook/tài liệu FE."
        ),
        "tags": [
            "documentation",
            "onboarding",
            "fastapi",
            "gpu",
            "mongodb",
            "uv",
        ],
        "complexity": "moderate",
        "languageNotes": "Markdown tiếng Việt; tham chiếu `config/settings.py` và scripts seed.",
    },
    "pyproject.toml": {
        "id": "config:pyproject.toml",
        "type": "config",
        "summary": (
            "Metadata dự án `kortek` (Python ≥3.10): pin dependency runtime "
            "(FastAPI, Motor, TensorRT cu12, Torch CUDA 128 qua uv index, Ultralytics, …) "
            "và pytest `testpaths=tests`."
        ),
        "tags": [
            "uv",
            "dependencies",
            "pytest",
            "pytorch-cu128",
            "packaging",
        ],
        "complexity": "moderate",
        "languageNotes": "Nguồn chính cho `uv sync`; `readme` trỏ README.md.",
    },
    "requirements.txt": {
        "id": "document:requirements.txt",
        "type": "document",
        "summary": (
            "Danh sách pip-style (legacy/tham khảo): AI vision, API stack, Mongo, Pillow; "
            "ghi chú cài Torch CUDA và FFmpeg NVDEC/TensorRT thủ công. "
            "Một số version khác `pyproject.toml` (vd. ultralytics 8.3.0)."
        ),
        "tags": [
            "documentation",
            "dependencies",
            "pip",
            "legacy",
            "cuda",
        ],
        "complexity": "simple",
        "languageNotes": "Bỏ qua bởi extract; đọc trực tiếp từ repo (~30 dòng comment + pins).",
    },
}

README_DOC_TARGETS: list[tuple[str, str, float]] = [
    (ENTRY_APP, "documents", 1.0),
    (ENTRY_MAIN, "documents", 0.85),
    ("file:config/settings.py", "documents", 0.9),
    ("file:scripts/seed_users.py", "documents", 0.85),
    ("file:scripts/seed_db.py", "documents", 0.75),
]

CONFIG_TARGETS: list[tuple[str, str, float]] = [
    (ENTRY_APP, "configures", 1.0),
    (ENTRY_MAIN, "configures", 0.9),
]

REQ_TARGETS: list[tuple[str, str, float]] = [
    (ENTRY_APP, "documents", 0.7),
]


def slug_heading(path: str, heading: str) -> str:
    safe = re.sub(r"[^\w\-]+", "-", heading.strip(), flags=re.UNICODE).strip("-").lower()
    safe = re.sub(r"-+", "-", safe)[:80] or "section"
    return f"section:{path}:{safe}"


def complexity_from_lines(non_empty: int) -> str:
    if non_empty < 40:
        return "simple"
    if non_empty <= 100:
        return "moderate"
    return "complex"


def section_summary(path: str, heading: str) -> str:
    h = heading.lower()
    if path == "README.md":
        if "yêu cầu" in h or "thiết bị" in h:
            return "Bảng yêu cầu phần cứng/phần mềm: Windows, Python, uv, MongoDB, GPU CUDA, TensorRT, FFmpeg NVDEC."
        if "chạy lần đầu" in h or "clone" in h:
            return "Quy trình setup từ clone repo đến chạy API lần đầu."
        if "dependency" in h or "cài" in h:
            return "Hướng dẫn `uv sync` và cài PyTorch wheel CUDA 128."
        if ".env" in h:
            return "Mẫu biến môi trường server, Mongo, JWT, MODEL_PATH và ghi chú ICS."
        if "mongodb" in h:
            return "Yêu cầu MongoDB local đúng port (mặc định 27018)."
        if "seed user" in h:
            return "Tạo user admin/operator/viewer qua `scripts/seed_users.py`."
        if "seed camera" in h or "mock" in h:
            return "Seed dữ liệu camera giả tùy chọn với `scripts/seed_db.py`."
        if "chạy api" in h:
            return "Lệnh `uv run uvicorn app:app` và endpoint Swagger/login."
        if "kiểm tra" in h:
            return "Smoke test health, login và điều kiện inference GPU."
        if "cấu trúc" in h:
            return "Bảng tóm tắt thư mục domain/application/infrastructure/presentation."
        if "tài liệu fe" in h:
            return "Link tài liệu zone runtime flags cho frontend."
        if "vận hành" in h:
            return "Link runbook runtime product (start-scan, degraded, sự cố)."
        if "ghi chú" in h:
            return "Cảnh báo `.env`/model, hạn chế thiếu CUDA và JWT dev."
        if "layered" in h or "architecture" in h:
            return "Giới thiệu hệ thống dispatch camera AMR và API `/api/v1`."
    if path == "pyproject.toml":
        if heading == "project":
            return "Tên package, version, requires-python và mảng dependencies runtime."
        if "optional" in heading:
            return "Nhóm dev dependency (pytest)."
        if "tool.uv.index" in heading:
            return "Index PyTorch CUDA 128 explicit cho uv."
        if "tool.uv.sources" in heading:
            return "Ánh xạ torch/torchvision/torchaudio sang index pytorch-cu128."
        if "pytest" in heading:
            return "Cấu hình pytest: testpaths tests, pythonpath root."
    return f"Mục «{heading}» trong `{path}`."


def main() -> None:
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    inp = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    batch_paths = {f["path"] for f in inp["batchFiles"]}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    def add_node(node: dict[str, Any]) -> None:
        if node["id"] in seen_nodes:
            return
        seen_nodes.add(node["id"])
        nodes.append(node)

    def add_edge(source: str, target: str, etype: str, weight: float) -> None:
        if source == target:
            return
        edges.append(
            {
                "source": source,
                "target": target,
                "type": etype,
                "direction": "forward",
                "weight": weight,
            }
        )

    by_path = {r["path"]: r for r in extract.get("results") or []}

    for path in ("README.md", "pyproject.toml", "requirements.txt"):
        if path not in batch_paths:
            continue
        meta = FILE_NODES[path]
        name = Path(path).name
        rec = by_path.get(path)
        non_empty = rec["nonEmptyLines"] if rec else (
            25 if path == "requirements.txt" else 50
        )
        complexity = meta.get("complexity") or complexity_from_lines(non_empty)
        node: dict[str, Any] = {
            "id": meta["id"],
            "type": meta["type"],
            "name": name,
            "filePath": path,
            "summary": meta["summary"],
            "tags": meta["tags"],
            "complexity": complexity,
        }
        if meta.get("languageNotes"):
            node["languageNotes"] = meta["languageNotes"]
        add_node(node)

        if rec:
            for sec in rec.get("sections") or []:
                heading = sec.get("heading") or ""
                sid = slug_heading(path, heading)
                line = sec.get("line") or 1
                add_node(
                    {
                        "id": sid,
                        "type": "section",
                        "name": heading,
                        "filePath": path,
                        "lineRange": [line, line],
                        "summary": section_summary(path, heading),
                        "tags": ["section", "documentation" if meta["type"] == "document" else "config"],
                        "complexity": "simple",
                    }
                )
                add_edge(meta["id"], sid, "contains", 1.0)

    readme_id = FILE_NODES["README.md"]["id"]
    for target, etype, weight in README_DOC_TARGETS:
        add_edge(readme_id, target, etype, weight)

    pyproject_id = FILE_NODES["pyproject.toml"]["id"]
    for target, etype, weight in CONFIG_TARGETS:
        add_edge(pyproject_id, target, etype, weight)
    add_edge(pyproject_id, readme_id, "references", 0.8)

    req_id = FILE_NODES["requirements.txt"]["id"]
    for target, etype, weight in REQ_TARGETS:
        add_edge(req_id, target, etype, weight)
    add_edge(req_id, pyproject_id, "references", 0.65)

    out = {"nodes": nodes, "edges": edges}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"nodes={len(nodes)} edges={len(edges)} -> {OUT_PATH}")


if __name__ == "__main__":
    main()
