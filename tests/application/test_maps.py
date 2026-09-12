"""Map zip import / compress / version retention."""
from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path

from application.fe_api.maps import (
    DownloadMapZip,
    GetCompress,
    ImportMap,
    ListMapVersions,
    SetActiveMap,
)
from application.null_ports import NullMapStateStore, NullMapVersionStore
from infrastructure.storage.map_zip_store import MapZipStore, find_compress_entry, validate_zip_has_compress


def _run(coro):
    return asyncio.run(coro)


def _mini_zip_with_compress(compress: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "compress/compress.json",
            __import__("json").dumps(compress),
        )
    return buf.getvalue()


def test_find_compress_entry():
    assert find_compress_entry(["compress/compress.json"]) == "compress/compress.json"
    assert find_compress_entry(["compress.json"]) is None
    assert find_compress_entry(["a/b/compress.json"]) == "a/b/compress.json"


def test_validate_requires_compress(tmp_path):
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("readme.txt", "x")
    try:
        validate_zip_has_compress(bad.getvalue())
        assert False, "expected ValueError"
    except ValueError as e:
        assert "compress.json" in str(e)


def test_import_set_active_get_compress_prune(tmp_path):
    store = MapZipStore(str(tmp_path))
    versions = NullMapVersionStore()
    state = NullMapStateStore()
    # Fake created_at ordering: NullMapVersionStore uses list order as oldest-first
    importer = ImportMap(versions, state, store, keep=2, max_upload_mb=10)

    compress = {"nodeKeys": ["x"], "nodeArr": [[1]]}
    raw = _mini_zip_with_compress(compress)

    r1 = _run(importer.execute(raw, "a.zip", "admin"))
    assert r1.success
    v1 = r1.data["versionId"]
    assert state.active == v1

    r2 = _run(importer.execute(raw, "b.zip", "admin"))
    v2 = r2.data["versionId"]
    r3 = _run(importer.execute(raw, "c.zip", "admin"))
    v3 = r3.data["versionId"]
    assert r3.data["isActive"] is True
    assert state.active == v3
    # keep=2 → pruned oldest
    assert _run(versions.count_all()) == 2
    assert v1 in r3.data["pruned"]
    ids = {r["version_id"] for r in versions.rows}
    assert v1 not in ids
    assert v2 in ids and v3 in ids

    got = _run(GetCompress(versions, state, store).execute())
    assert got.data["versionId"] == v3
    assert got.data["compress"]["nodeArr"] == [[1]]

    listed = _run(ListMapVersions(versions, state).execute())
    assert listed.data["activeVersionId"] == v3
    assert sum(1 for i in listed.data["items"] if i["isActive"]) == 1

    _run(SetActiveMap(versions, state).execute(v2))
    assert state.active == v2

    dl = _run(DownloadMapZip(versions, state, store).execute(v2))
    assert dl.success
    assert dl.data["content"][:2] == b"PK"


def test_import_real_0805_if_present():
    sample = Path("data/0805.zip")
    if not sample.is_file():
        return
    data = sample.read_bytes()
    entry, compress = validate_zip_has_compress(data)
    assert entry.endswith("/compress.json")
    assert "nodeArr" in compress
