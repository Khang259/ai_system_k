#!/usr/bin/env python3
"""Inline knowledge-graph validator (Phase 6)."""
import json
import sys
from collections import Counter
from pathlib import Path

graph_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

graph = json.loads(graph_path.read_text(encoding="utf-8"))
issues = []
warnings = []

if not isinstance(graph.get("nodes"), list):
    issues.append("graph.nodes is missing or not an array")
    graph["nodes"] = []
if not isinstance(graph.get("edges"), list):
    issues.append("graph.edges is missing or not an array")
    graph["edges"] = []

node_ids = set()
seen = {}
for i, n in enumerate(graph["nodes"]):
    nid = n.get("id")
    if not nid:
        issues.append(f"Node[{i}] missing id")
        continue
    if not n.get("type"):
        issues.append(f"Node[{i}] '{nid}' missing type")
    if not n.get("name"):
        issues.append(f"Node[{i}] '{nid}' missing name")
    if not n.get("summary"):
        issues.append(f"Node[{i}] '{nid}' missing summary")
    if not n.get("tags"):
        issues.append(f"Node[{i}] '{nid}' missing tags")
    if nid in seen:
        issues.append(f"Duplicate node ID '{nid}' at indices {seen[nid]} and {i}")
    else:
        seen[nid] = i
    node_ids.add(nid)

for i, e in enumerate(graph["edges"]):
    if e.get("source") not in node_ids:
        issues.append(f"Edge[{i}] source '{e.get('source')}' not found")
    if e.get("target") not in node_ids:
        issues.append(f"Edge[{i}] target '{e.get('target')}' not found")

file_level_types = {
    "file",
    "config",
    "document",
    "service",
    "pipeline",
    "table",
    "schema",
    "resource",
    "endpoint",
}
file_nodes = [n["id"] for n in graph["nodes"] if n.get("type") in file_level_types]

if not isinstance(graph.get("layers"), list):
    if graph.get("layers"):
        warnings.append("graph.layers is not an array")
    graph["layers"] = []
if not isinstance(graph.get("tour"), list):
    if graph.get("tour"):
        warnings.append("graph.tour is not an array")
    graph["tour"] = []

assigned = {}
for layer in graph["layers"]:
    for nid in layer.get("nodeIds") or []:
        if nid not in node_ids:
            issues.append(f"Layer '{layer.get('id')}' refs missing node '{nid}'")
        if nid in assigned:
            issues.append(f"Node '{nid}' appears in multiple layers")
        assigned[nid] = layer.get("id")

for nid in file_nodes:
    if nid not in assigned:
        issues.append(f"File node '{nid}' not in any layer")

for i, step in enumerate(graph["tour"]):
    for nid in step.get("nodeIds") or []:
        if nid not in node_ids:
            issues.append(f"Tour step[{i}] refs missing node '{nid}'")

with_edges = set()
for e in graph["edges"]:
    with_edges.add(e.get("source"))
    with_edges.add(e.get("target"))
for n in graph["nodes"]:
    if n.get("id") not in with_edges:
        warnings.append(f"Node '{n.get('id')}' has no edges (orphan)")

stats = {
    "totalNodes": len(graph["nodes"]),
    "totalEdges": len(graph["edges"]),
    "totalLayers": len(graph["layers"]),
    "tourSteps": len(graph["tour"]),
    "nodeTypes": dict(Counter(n.get("type") for n in graph["nodes"])),
    "edgeTypes": dict(Counter(e.get("type") for e in graph["edges"])),
}

output_path.write_text(
    json.dumps({"issues": issues, "warnings": warnings, "stats": stats}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"issues={len(issues)} warnings={len(warnings)}")
