"""Enforce layer boundaries — domain không phụ thuộc tầng ngoài."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "domain"

FORBIDDEN_ROOTS = {
    "fastapi",
    "motor",
    "torch",
    "ultralytics",
    "cv2",
    "requests",
    "infrastructure",
    "presentation",
    "application",
    "core",
    "service",
}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_does_not_import_outer_layers():
    violations = []
    for path in DOMAIN.rglob("*.py"):
        for root in _imported_roots(path) & FORBIDDEN_ROOTS:
            violations.append(f"{path.relative_to(ROOT)} imports {root}")
    assert violations == []


def test_core_folder_removed():
    assert not (ROOT / "core").exists()
    assert not (ROOT / "service").exists()
    assert not (ROOT / "utils" / "data.py").exists()
