# -*- coding: utf-8 -*-
"""Generate batch-1.json for Understand-Anything (UTF-8 no BOM)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"d:\Prj\kortek")
UA = ROOT / ".ua"
EXTRACT = UA / "tmp" / "ua-file-extract-results-1.json"
INPUT = UA / "tmp" / "ua-file-analyzer-input-1.json"
BATCHES = UA / "intermediate" / "batches.json"
OUT = UA / "intermediate" / "batch-1.json"


def complexity_from_lines(non_empty: int) -> str:
    if non_empty < 50:
        return "simple"
    if non_empty <= 200:
        return "moderate"
    return "complex"


def complexity_fn(lines: int) -> str:
    if lines < 15:
        return "simple"
    if lines <= 40:
        return "moderate"
    return "complex"


FILE_SUMMARIES: dict[str, tuple[str, list[str], str | None]] = {
    "application/auth/__init__.py": (
        "Barrel package xác thực: re-export các use case session từ session.py cho container và presentation.",
        ["barrel", "auth", "entry-point", "session"],
        "Python __init__ re-export pattern cho lớp application.",
    ),
    "application/auth/session.py": (
        "Use case đăng nhập, đăng xuất, refresh token và lấy thông tin user; tích hợp audit và rate-limit thất bại.",
        ["auth", "session", "use-case", "jwt"],
        None,
    ),
    "application/cameras/preview.py": (
        "Use case lấy frame preview và metadata stream camera qua port FrameProvider cho UI giám sát.",
        ["camera", "preview", "use-case", "webrtc"],
        None,
    ),
    "application/fe_api/__init__.py": (
        "Barrel tập trung toàn bộ use case frontend /api/v1: camera, map, log, node, pair, poll, zone.",
        ["barrel", "fe-api", "use-case", "entry-point"],
        None,
    ),
    "application/fe_api/cameras.py": (
        "Barrel gom các use case camera/ROI từ module con để presentation import một điểm.",
        ["barrel", "camera", "fe-api"],
        None,
    ),
    "application/fe_api/cameras_crud.py": (
        "Use case tạo và xóa camera: validate RTSP, priority start, đồng bộ node/pair và audit.",
        ["camera", "crud", "use-case", "validation"],
        None,
    ),
    "application/fe_api/cameras_helpers.py": (
        "Helper nội bộ cho luồng camera: chuẩn hóa node quan sát, priority, kiểm tra RTSP trùng.",
        ["camera", "helper", "validation", "priority"],
        None,
    ),
    "application/fe_api/cameras_read.py": (
        "Use case đọc danh sách camera và ROI, map sang DTO cho frontend.",
        ["camera", "read", "use-case", "mapper"],
        None,
    ),
    "application/fe_api/cameras_status.py": (
        "Use case bật/tắt camera và cascade rule đồng bộ inference/node khi đổi trạng thái.",
        ["camera", "status", "use-case", "sync-rules"],
        None,
    ),
    "application/fe_api/cameras_update.py": (
        "Use case cập nhật cấu hình camera: zone, RTSP, priority và đồng bộ node liên quan.",
        ["camera", "update", "use-case", "validation"],
        None,
    ),
    "application/fe_api/log_mappers.py": (
        "Pure mapper chuyển document Mongo/audit sang payload JSON cho màn hình log và notification.",
        ["mapper", "logs", "serialization", "utility"],
        None,
    ),
    "application/fe_api/logs.py": (
        "Use case paginate audit, user action, system action, notification và snapshot theo order.",
        ["logs", "audit", "use-case", "pagination"],
        None,
    ),
    "application/fe_api/mappers.py": (
        "Mapper dùng chung cho node label, trạng thái camera và ROI bounding box.",
        ["mapper", "fe-api", "validation", "utility"],
        None,
    ),
    "application/fe_api/maps.py": (
        "Use case import/list/active map bản đồ AMR, nén zip và tải xuống qua MapZipStore.",
        ["map", "use-case", "storage", "amr"],
        None,
    ),
    "application/fe_api/nodes.py": (
        "Use case quản lý node AMR: đọc, maintenance, khóa user/system và cập nhật priority.",
        ["node", "dispatch", "use-case", "lock"],
        None,
    ),
    "application/fe_api/pairs.py": (
        "Use case CRUD cặp start/end node cho điều phối, validate node và sync rule khi bật/tắt.",
        ["pair", "dispatch", "use-case", "validation"],
        None,
    ),
    "application/fe_api/poll.py": (
        "Use case long-poll snapshot gộp camera, zone, notification, map state và runtime node với ETag.",
        ["poll", "fe-api", "etag", "snapshot"],
        None,
    ),
    "application/fe_api/priority_rules.py": (
        "Rule kiểm tra priority start/end unique theo zone trước khi tạo hoặc sửa node/camera.",
        ["priority", "validation", "rule", "zone"],
        None,
    ),
    "application/fe_api/rois.py": (
        "Use case tạo/sửa/xóa ROI gắn camera-node, validate box và đồng bộ khi inference đang chạy.",
        ["roi", "camera", "use-case", "validation"],
        None,
    ),
    "application/fe_api/runtime_nodes.py": (
        "Use case đọc trạng thái runtime node từ RuntimeStateHub cho dashboard frontend.",
        ["runtime", "node", "use-case", "hub"],
        None,
    ),
    "application/fe_api/sync_rules.py": (
        "Rule đồng bộ side-effect: pause inference, cascade xóa node/pair khi cấu hình thay đổi.",
        ["sync-rules", "cascade", "inference", "validation"],
        None,
    ),
    "application/fe_api/zones.py": (
        "Use case liệt kê zone phục vụ cấu hình camera và node trên frontend.",
        ["zone", "read", "use-case", "fe-api"],
        None,
    ),
    "application/ports.py": (
        "Tập Protocol (port) hexagonal: repository, runtime, auth, dispatch — infrastructure implement.",
        ["ports", "protocol", "hexagonal", "type-definition"],
        "typing.Protocol tách application khỏi Mongo, YOLO và HTTP cụ thể.",
    ),
    "application/result.py": (
        "Dataclass UseCaseResult chuẩn hóa success/error/data và map sang JSON HTTP cho presentation.",
        ["result", "use-case", "serialization", "utility"],
        None,
    ),
    "application/runtime/__init__.py": (
        "Barrel runtime: re-export control, health và RuntimeStateHub cho container.",
        ["barrel", "runtime", "entry-point"],
        None,
    ),
    "application/runtime/control.py": (
        "Use case start/stop/reload pipeline inference và truy vấn trạng thái runtime GPU.",
        ["runtime", "control", "use-case", "inference"],
        None,
    ),
    "application/runtime/health.py": (
        "Use case health check tổng hợp DB và runtime cho endpoint /health.",
        ["health", "runtime", "use-case", "monitoring"],
        None,
    ),
    "application/runtime/runtime_state_hub.py": (
        "Hub in-memory giữ snapshot trạng thái node runtime và map sang item cho poll API.",
        ["runtime", "hub", "state", "singleton"],
        None,
    ),
    "application/state/reset_flags.py": (
        "Use case ghi/clear cờ reset theo order_id phục vụ luồng hủy batch dispatch.",
        ["reset", "dispatch", "use-case", "state"],
        None,
    ),
}


def symbol_summary(path: str, name: str, kind: str) -> tuple[str, list[str]]:
    key = f"{path}:{name}"
    PORTS = {
        "CameraConfigRepository": (
            "Port truy cập cấu hình camera và ROI trong persistence.",
            ["port", "camera", "repository"],
        ),
        "PairsRepositoryPort": (
            "Port CRUD và truy vấn cặp node start/end theo zone.",
            ["port", "pair", "repository"],
        ),
        "NodeRepositoryPort": (
            "Port quản lý node AMR: lock, maintenance, priority và zone.",
            ["port", "node", "repository"],
        ),
        "ZoneRepositoryPort": (
            "Port đọc danh sách zone cấu hình.",
            ["port", "zone", "repository"],
        ),
        "ActionAuditPort": (
            "Port ghi audit hành động người dùng trên hệ thống.",
            ["port", "audit", "logging"],
        ),
        "SystemActionAuditPort": (
            "Port ghi log hành động hệ thống tự động.",
            ["port", "audit", "system"],
        ),
        "CameraRuntime": (
            "Port điều khiển vòng đời stream/camera runtime.",
            ["port", "camera", "runtime"],
        ),
        "InferencePort": (
            "Port bật/tắt và trạng thái pipeline inference GPU.",
            ["port", "inference", "gpu"],
        ),
        "NodeStateStore": (
            "Port lưu trạng thái node realtime cho dispatch.",
            ["port", "node", "state"],
        ),
        "DispatchGateway": (
            "Port gửi lệnh dispatch tới ICS/AMR backend.",
            ["port", "dispatch", "gateway"],
        ),
        "IcsOrderQueryPort": (
            "Port truy vấn trạng thái order từ ICS.",
            ["port", "ics", "order"],
        ),
        "RuntimeControl": (
            "Port điều khiển start/stop/reload runtime service.",
            ["port", "runtime", "control"],
        ),
        "DbHealthPort": (
            "Port ping kết nối database.",
            ["port", "health", "database"],
        ),
        "WebrtcRunnerPort": (
            "Port quản lý session WebRTC preview.",
            ["port", "webrtc", "preview"],
        ),
        "UserRepositoryPort": (
            "Port truy cập user và credential.",
            ["port", "auth", "user"],
        ),
        "RefreshTokenStore": (
            "Port lưu và thu hồi refresh token.",
            ["port", "auth", "token"],
        ),
        "PasswordHasher": (
            "Port hash và verify mật khẩu.",
            ["port", "auth", "security"],
        ),
        "TokenIssuer": (
            "Port phát access/refresh JWT.",
            ["port", "auth", "jwt"],
        ),
        "AuthAuditPort": (
            "Port audit sự kiện đăng nhập/đăng xuất.",
            ["port", "auth", "audit"],
        ),
        "FrameProvider": (
            "Port lấy frame hoặc metadata preview camera.",
            ["port", "camera", "preview"],
        ),
    }
    if path == "application/ports.py" and name in PORTS:
        return PORTS[name]

    OVERRIDES: dict[str, tuple[str, list[str]]] = {
        "application/auth/session.py:public_user": (
            "Map document user Mongo sang dict public (ẩn hash, thêm permissions).",
            ["auth", "mapper", "user"],
        ),
        "application/auth/session.py:_is_expired": (
            "Kiểm tra refresh token đã hết hạn so với UTC now.",
            ["auth", "token", "utility"],
        ),
        "application/auth/session.py:Login": (
            "Use case đăng nhập: validate user, hash password, audit và phát token.",
            ["auth", "login", "use-case"],
        ),
        "application/auth/session.py:Logout": (
            "Use case đăng xuất và thu hồi refresh token.",
            ["auth", "logout", "use-case"],
        ),
        "application/auth/session.py:RefreshSession": (
            "Use case đổi refresh token lấy access token mới.",
            ["auth", "refresh", "use-case"],
        ),
        "application/auth/session.py:GetMe": (
            "Use case trả profile user hiện tại sau xác thực.",
            ["auth", "profile", "use-case"],
        ),
        "application/result.py:UseCaseResult": (
            "Kết quả chuẩn use case với factory ok/fail và to_http().",
            ["result", "dataclass", "http"],
        ),
        "application/fe_api/poll.py:compute_etag": (
            "Tính ETag hash từ snapshot poll để client cache có điều kiện.",
            ["poll", "etag", "hash"],
        ),
        "application/fe_api/poll.py:GetPollSnapshot": (
            "Gom dữ liệu poll từ nhiều use case con và trả snapshot + etag.",
            ["poll", "snapshot", "use-case"],
        ),
        "application/runtime/runtime_state_hub.py:RuntimeStateHub": (
            "Singleton hub cập nhật và đọc map trạng thái node runtime.",
            ["runtime", "hub", "state"],
        ),
        "application/runtime/runtime_state_hub.py:map_runtime_item": (
            "Map bản ghi runtime nội bộ sang dict cho API poll.",
            ["runtime", "mapper", "utility"],
        ),
    }
    if key in OVERRIDES:
        return OVERRIDES[key]

    if kind == "class":
        if name.startswith("Get") and not name.startswith("GetMe"):
            rest = re.sub(r"^Get", "", name)
            return (
                f"Use case đọc {rest} cho frontend, trả về UseCaseResult.",
                ["use-case", "read", "fe-api"],
            )
        if name.startswith("Set") or name.startswith("Update") or name.startswith("Create"):
            return (
                f"Use case ghi cấu hình {name} qua port repository và rule đồng bộ.",
                ["use-case", "write", "fe-api"],
            )
        if name.startswith("Delete"):
            return (
                f"Use case xóa {name[6:]} kèm cascade rule khi cần.",
                ["use-case", "delete", "fe-api"],
            )
        if name.endswith("Store") or name.endswith("Port"):
            return (
                f"Lớp/port hỗ trợ persistence hoặc adapter cho {name}.",
                ["adapter", "persistence", "fe-api"],
            )
        if "Fe" in name:
            return (
                f"Biến thể use case pair cho API frontend ({name}).",
                ["pair", "use-case", "fe-api"],
            )
        return (
            f"Lớp use case hoặc helper {name} trong lớp application.",
            ["use-case", "class", "application"],
        )

    # function
    if name.startswith("_"):
        return (
            f"Hàm nội bộ {name} hỗ trợ validation hoặc map dữ liệu.",
            ["helper", "internal", "utility"],
        )
    return (
        f"Hàm {name} xử lý logic nghiệp vụ hoặc map dữ liệu cho FE API.",
        ["utility", "fe-api", "helper"],
    )


def is_exported(result: dict, name: str) -> bool:
    return any(e.get("name") == name for e in (result.get("exports") or []))


def main() -> None:
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    inp = json.loads(INPUT.read_text(encoding="utf-8"))
    batches = json.loads(BATCHES.read_text(encoding="utf-8"))
    batch1 = next(b for b in batches["batches"] if b["batchIndex"] == 1)
    neighbor_map = batch1.get("neighborMap") or {}
    import_data = inp["batchImportData"]

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(node: dict) -> None:
        nodes.append(node)
        node_ids.add(node["id"])

    def add_edge(source: str, target: str, etype: str, weight: float) -> None:
        edges.append(
            {
                "source": source,
                "target": target,
                "type": etype,
                "direction": "forward",
                "weight": weight,
            }
        )

    for result in extract["results"]:
        path = result["path"]
        file_id = f"file:{path}"
        name = Path(path).name
        ne = result.get("nonEmptyLines") or result.get("totalLines") or 0
        fs, ftags, flnotes = FILE_SUMMARIES.get(
            path,
            (
                f"Module Python {path} trong lớp application.",
                ["application", "python", "module"],
                None,
            ),
        )
        file_node: dict = {
            "id": file_id,
            "type": "file",
            "name": name,
            "filePath": path,
            "summary": fs,
            "tags": ftags,
            "complexity": complexity_from_lines(ne),
        }
        if flnotes:
            file_node["languageNotes"] = flnotes
        add_node(file_node)

        for fn in result.get("functions") or []:
            lines = fn["endLine"] - fn["startLine"] + 1
            if lines < 10 and not is_exported(result, fn["name"]):
                continue
            fid = f"function:{path}:{fn['name']}"
            summary, tags = symbol_summary(path, fn["name"], "function")
            add_node(
                {
                    "id": fid,
                    "type": "function",
                    "name": fn["name"],
                    "filePath": path,
                    "lineRange": [fn["startLine"], fn["endLine"]],
                    "summary": summary,
                    "tags": tags,
                    "complexity": complexity_fn(lines),
                }
            )
            add_edge(file_id, fid, "contains", 1.0)
            if is_exported(result, fn["name"]):
                add_edge(file_id, fid, "exports", 0.8)

        for cls in result.get("classes") or []:
            lines = cls["endLine"] - cls["startLine"] + 1
            methods = len(cls.get("methods") or [])
            if methods < 2 and lines < 20 and not is_exported(result, cls["name"]):
                continue
            cid = f"class:{path}:{cls['name']}"
            summary, tags = symbol_summary(path, cls["name"], "class")
            add_node(
                {
                    "id": cid,
                    "type": "class",
                    "name": cls["name"],
                    "filePath": path,
                    "lineRange": [cls["startLine"], cls["endLine"]],
                    "summary": summary,
                    "tags": tags,
                    "complexity": complexity_fn(lines),
                }
            )
            add_edge(file_id, cid, "contains", 1.0)
            if is_exported(result, cls["name"]):
                add_edge(file_id, cid, "exports", 0.8)

    # imports — one edge per batchImportData entry
    for file_path, targets in import_data.items():
        src = f"file:{file_path}"
        for tgt in targets:
            add_edge(src, f"file:{tgt}", "imports", 0.7)

    # calls: UseCaseResult từ use case có execute (một cạnh mỗi class)
    uc_id = "class:application/result.py:UseCaseResult"
    for result in extract["results"]:
        path = result["path"]
        callees = {
            e.get("callee")
            for e in (result.get("callGraph") or [])
            if e.get("callee") in ("UseCaseResult.ok", "UseCaseResult.fail")
        }
        if not callees:
            continue
        for cls in result.get("classes") or []:
            if "execute" in (cls.get("methods") or []):
                cid = f"class:{path}:{cls['name']}"
                if cid in node_ids:
                    add_edge(cid, uc_id, "calls", 0.8)
        for entry in result.get("callGraph") or []:
            caller = entry.get("caller") or ""
            callee = entry.get("callee") or ""
            if callee in ("UseCaseResult.ok", "UseCaseResult.fail") and caller not in (
                "",
                "execute",
            ):
                src_fn = f"function:{path}:{caller}"
                if src_fn in node_ids:
                    add_edge(src_fn, uc_id, "calls", 0.8)

    # calls tới map_zip_store (neighborMap batch 3)
    maps_file = "application/fe_api/maps.py"
    zip_store = "infrastructure/storage/map_zip_store.py"
    for sym in ("find_compress_entry", "validate_zip_has_compress", "MapZipStore"):
        add_edge(f"file:{maps_file}", f"function:{zip_store}:{sym}", "calls", 0.8)

    # dedupe edges
    seen: set[tuple[str, str, str]] = set()
    unique_edges: list[dict] = []
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        if key in seen:
            continue
        seen.add(key)
        unique_edges.append(e)
    edges = unique_edges

    out = {"nodes": nodes, "edges": edges}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    imp_edges = sum(1 for e in edges if e["type"] == "imports")
    expected = sum(len(v) for v in import_data.values())
    print(
        json.dumps(
            {
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
                "importsEdgeCount": imp_edges,
                "expectedImports": expected,
                "importsMatch": imp_edges == expected,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
