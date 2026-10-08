"""Seed sandbox phải hợp lệ theo luật SSOT: node thuộc ROI camera, priority duy nhất trong zone."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from domain.dispatch.active_task import parse_order_id

_SPEC = importlib.util.spec_from_file_location(
    "seed_sandbox", Path(__file__).resolve().parents[1] / "scripts" / "seed_sandbox.py"
)
seed = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(seed)


def test_every_node_is_roi_of_its_camera():
    docs = seed.build_docs()
    rois_by_camera = {c["cameraId"]: set(c["rois"]) for c in docs["cameras"]}
    for node in docs["nodes"]:
        assert node["node_id"] in rois_by_camera[node["camera_id"]]


def test_start_priority_unique_per_zone():
    starts = [n for n in seed.build_docs()["nodes"] if n["node_type"] == "start"]
    keys = [(n["zone_id"], n["priority"]) for n in starts]
    assert len(keys) == len(set(keys)) == 20


def test_pairs_reference_existing_nodes():
    docs = seed.build_docs()
    node_ids = {n["node_id"] for n in docs["nodes"]}
    for pair in docs["pairs"]:
        assert {pair["start_point"], pair["end_point"]} <= node_ids


def test_one_end_per_zone_no_cross_zone_pairs():
    docs = seed.build_docs()
    ends = {n["node_id"]: n["zone_id"] for n in docs["nodes"] if n["node_type"] == "end"}
    starts = {n["node_id"]: n["zone_id"] for n in docs["nodes"] if n["node_type"] == "start"}
    assert set(ends.values()) == {"SBA", "SBB"}
    assert len(ends) == 2
    for pair in docs["pairs"]:
        assert starts[pair["start_point"]] == ends[pair["end_point"]]


def test_node_ids_survive_order_id_round_trip():
    """orderId chỉ giữ phần số → panel FE phải dựng lại đúng node_id."""
    for pair in seed.build_docs()["pairs"]:
        start_num = pair["start_point"].removeprefix("start_")
        end_num = pair["end_point"].removeprefix("end_")
        order_id = f"S-{start_num}-{end_num}-2026-10-06 17:00:00"
        assert parse_order_id(order_id) == (pair["start_point"], pair["end_point"])
