# -*- coding: utf-8 -*-
"""Build batch-2.json for Understand-Anything file-analyzer."""
import json
from pathlib import Path

ROOT = Path(r"d:\Prj\kortek")
UA = ROOT / ".ua"
EXTRACT = UA / "tmp" / "ua-file-extract-results-2.json"
INPUT = UA / "tmp" / "ua-file-analyzer-input-2.json"
OUTPUT = UA / "intermediate" / "batch-2.json"

with EXTRACT.open(encoding="utf-8") as f:
    extract = json.load(f)
with INPUT.open(encoding="utf-8") as f:
    inp = json.load(f)

batch_import = inp["batchImportData"]
export_names: dict[str, set[str]] = {}
by_path = {r["path"]: r for r in extract["results"]}

for r in extract["results"]:
    export_names[r["path"]] = {e["name"] for e in r.get("exports", [])}


def line_count(start: int, end: int) -> int:
    return end - start + 1


def fn_significant(path: str, fn: dict) -> bool:
    n = line_count(fn["startLine"], fn["endLine"])
    if n >= 10:
        return True
    return fn["name"] in export_names.get(path, set())


def cls_significant(path: str, cls: dict) -> bool:
    n = line_count(cls["startLine"], cls["endLine"])
    methods = cls.get("methods") or []
    if len(methods) >= 2 or n >= 20:
        return True
    return cls["name"] in export_names.get(path, set())


FILE_META = {
    "app.py": (
        "Factory FastAPI: lifespan gắn MongoDB, auth, runtime, MediaMTX/WebRTC và mount router /api/v1.",
        ["entry-point", "fastapi", "lifespan", "middleware"],
        "moderate",
        "Dùng asynccontextmanager cho startup/shutdown và CORSMiddleware.",
    ),
    "main.py": (
        "Điểm chạy Uvicorn: import app từ app.py (wrapper mỏng).",
        ["entry-point", "uvicorn", "bootstrap"],
        "simple",
        None,
    ),
    "infrastructure/auth/__init__.py": (
        "Barrel package auth: re-export adapter JWT, bcrypt, audit và ensure_auth_indexes.",
        ["barrel", "auth", "entry-point"],
        "simple",
        None,
    ),
    "infrastructure/auth/action_audit_adapter.py": (
        "Adapter ghi action log người dùng, redact field nhạy cảm trước khi lưu MongoDB.",
        ["auth", "audit", "adapter"],
        "moderate",
        None,
    ),
    "infrastructure/auth/audit_adapter.py": (
        "Adapter audit đăng nhập: log sự kiện và đếm failed login gần đây.",
        ["auth", "audit", "adapter"],
        "simple",
        None,
    ),
    "infrastructure/auth/indexes.py": (
        "Tạo MongoDB index cho users và refresh tokens khi app khởi động.",
        ["auth", "mongodb", "indexes"],
        "simple",
        None,
    ),
    "infrastructure/auth/jwt_service.py": (
        "JwtTokenService: phát access JWT, refresh token và hash refresh cho lưu DB.",
        ["auth", "jwt", "service"],
        "moderate",
        "Dùng PyJWT và secrets cho refresh token.",
    ),
    "infrastructure/auth/password_hasher.py": (
        "BcryptHasher bọc bcrypt hash/verify và dummy hash chống timing attack.",
        ["auth", "bcrypt", "security"],
        "simple",
        None,
    ),
    "infrastructure/auth/system_action_audit_adapter.py": (
        "Ghi dispatch/system action log async-safe từ thread/event loop khác.",
        ["audit", "dispatch", "adapter"],
        "moderate",
        "run_coroutine_threadsafe khi log từ worker thread.",
    ),
    "infrastructure/persistence/__init__.py": (
        "Barrel persistence: singleton repo MongoDB và hàm connect/disconnect.",
        ["barrel", "mongodb", "repository"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/base_repository.py": (
        "BaseRepository CRUD/pagination chung trên Motor collection.",
        ["mongodb", "repository", "data-access"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/db.py": (
        "Kết nối AsyncIOMotorClient singleton và truy cập database/collection.",
        ["mongodb", "motor", "connection"],
        "simple",
        None,
    ),
    "infrastructure/persistence/db_health.py": (
        "MongoHealthAdapter ping DB cho health check.",
        ["mongodb", "health", "adapter"],
        "simple",
        None,
    ),
    "infrastructure/persistence/camera_repository.py": (
        "CRUD camera, ROI và bật/tắt theo zone trên collection cameras.",
        ["mongodb", "camera", "repository"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/dispatch_log_repository.py": (
        "Lưu log dispatch, thống kê theo ngày và hiệu năng cặp node.",
        ["dispatch", "mongodb", "repository"],
        "moderate",
        "Aggregation pipeline cho thống kê zone.",
    ),
    "infrastructure/persistence/log_repositories.py": (
        "ActionLogRepository và AuditLogRepository cho audit UI.",
        ["audit", "mongodb", "repository"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/map_repository.py": (
        "MapVersionRepository và MapStateRepository quản lý bản đồ AMR.",
        ["map", "mongodb", "repository"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/node_repository.py": (
        "NodeRepository: node start/end, lock, priority và truy vấn theo zone/camera.",
        ["dispatch", "node", "repository"],
        "complex",
        "Logic lock system vs manual trên document node.",
    ),
    "infrastructure/persistence/notification_repository.py": (
        "Thông báo in-app: tạo, phân trang, đánh dấu đã đọc.",
        ["notification", "mongodb", "repository"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/pairs_repository.py": (
        "Quản lý cặp start-end dispatch theo zone và node.",
        ["dispatch", "pair", "repository"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/refresh_token_repository.py": (
        "Lưu/revoke refresh token hashed trong MongoDB.",
        ["auth", "mongodb", "repository"],
        "simple",
        None,
    ),
    "infrastructure/persistence/snapshot_repository.py": (
        "Snapshot inference: lưu, validate và thống kê false positive.",
        ["vision", "mongodb", "repository"],
        "moderate",
        None,
    ),
    "infrastructure/persistence/user_repository.py": (
        "UserRepository tra cứu và cập nhật tài khoản đăng nhập.",
        ["auth", "mongodb", "repository"],
        "simple",
        None,
    ),
    "infrastructure/persistence/zone_repository.py": (
        "ZoneRepository CRUD zone và kiểm tra enabled.",
        ["zone", "mongodb", "repository"],
        "simple",
        None,
    ),
    "scripts/seed_users.py": (
        "Script CLI seed/cập nhật user MongoDB theo role và permissions.",
        ["script", "auth", "seed"],
        "moderate",
        "Dùng pymongo sync (không Motor) cho tooling.",
    ),
}

FN_META = {
    ("app.py", "lifespan"): (
        "Startup/shutdown FastAPI: bind DI container, DB, auth, runtime, MediaMTX và retention.",
        ["lifespan", "startup", "dependency-injection"],
        "complex",
    ),
    ("app.py", "create_app"): (
        "Tạo FastAPI, CORS, handler lỗi JSON và gắn toàn bộ router v1.",
        ["fastapi", "factory", "routing"],
        "moderate",
    ),
    ("infrastructure/auth/action_audit_adapter.py", "_redact"): (
        "Loại bỏ/mask key password/token trong payload audit.",
        ["utility", "security", "redaction"],
        "simple",
    ),
    ("infrastructure/auth/indexes.py", "ensure_auth_indexes"): (
        "Đảm bảo index unique username và TTL refresh token.",
        ["mongodb", "indexes", "auth"],
        "simple",
    ),
    ("infrastructure/persistence/base_repository.py", "_now"): (
        "Timestamp UTC hiện tại cho created_at/updated_at.",
        ["utility", "datetime", "mongodb"],
        "simple",
    ),
    ("infrastructure/persistence/base_repository.py", "_serialize"): (
        "Chuyển document MongoDB sang dict JSON-safe (ObjectId -> str).",
        ["serialization", "mongodb", "utility"],
        "simple",
    ),
    ("infrastructure/persistence/db.py", "connect"): (
        "Khởi tạo Motor client và chọn database.",
        ["mongodb", "connection", "motor"],
        "simple",
    ),
    ("infrastructure/persistence/db.py", "disconnect"): (
        "Đóng Motor client khi app tắt.",
        ["mongodb", "connection", "shutdown"],
        "simple",
    ),
    ("infrastructure/persistence/db.py", "get_db"): (
        "Trả database handle hoặc RuntimeError nếu chưa connect.",
        ["mongodb", "accessor", "singleton"],
        "simple",
    ),
    ("infrastructure/persistence/db.py", "get_collection"): (
        "Lấy collection theo tên qua get_db().",
        ["mongodb", "accessor", "collection"],
        "simple",
    ),
    ("scripts/seed_users.py", "_read_password"): (
        "Đọc mật khẩu qua getpass với xác nhận lần hai.",
        ["cli", "security", "input"],
        "simple",
    ),
    ("scripts/seed_users.py", "_build_doc"): (
        "Dựng document user mới với UUID và permissions theo role.",
        ["seed", "user", "permissions"],
        "simple",
    ),
    ("scripts/seed_users.py", "_perm_diff"): (
        "So sánh hai tập permission để log thay đổi khi update.",
        ["utility", "permissions", "seed"],
        "simple",
    ),
    ("scripts/seed_users.py", "main"): (
        "Vòng lặp seed: insert hoặc update user và in diff permissions.",
        ["cli", "seed", "mongodb"],
        "moderate",
    ),
}

CLS_META = {
    ("infrastructure/auth/action_audit_adapter.py", "ActionAuditAdapter"): (
        "Ghi action log qua ActionLogRepository sau khi redact payload.",
        ["adapter", "audit", "logging"],
        "simple",
    ),
    ("infrastructure/auth/audit_adapter.py", "AuthAuditAdapter"): (
        "Facade audit login gọi AuditLogRepository.",
        ["adapter", "auth", "audit"],
        "simple",
    ),
    ("infrastructure/auth/jwt_service.py", "JwtTokenService"): (
        "Phát và decode JWT access; tạo/hash refresh token.",
        ["jwt", "auth", "service"],
        "moderate",
    ),
    ("infrastructure/auth/password_hasher.py", "BcryptHasher"): (
        "Hash và verify mật khẩu bằng bcrypt.",
        ["bcrypt", "auth", "security"],
        "simple",
    ),
    ("infrastructure/auth/system_action_audit_adapter.py", "SystemActionAuditAdapter"): (
        "Ghi dispatch log hệ thống, hỗ trợ gọi từ thread ngoài event loop.",
        ["audit", "dispatch", "async"],
        "moderate",
    ),
    ("infrastructure/persistence/base_repository.py", "BaseRepository"): (
        "Lớp cơ sở find/insert/update/delete/count cho mọi collection.",
        ["repository", "mongodb", "crud"],
        "moderate",
    ),
    ("infrastructure/persistence/db_health.py", "MongoHealthAdapter"): (
        "ping MongoDB command cho readiness probe.",
        ["health", "mongodb", "adapter"],
        "simple",
    ),
    ("infrastructure/persistence/camera_repository.py", "CameraRepository"): (
        "Truy vấn và cập nhật camera/ROI theo area, zone và camera_id.",
        ["camera", "repository", "roi"],
        "moderate",
    ),
    ("infrastructure/persistence/dispatch_log_repository.py", "DispatchLogRepository"): (
        "Persistence log dispatch và metric hoàn thành/thất bại.",
        ["dispatch", "repository", "metrics"],
        "moderate",
    ),
    ("infrastructure/persistence/log_repositories.py", "ActionLogRepository"): (
        "Lưu và truy vấn action log theo user/thời gian.",
        ["audit", "repository", "action-log"],
        "moderate",
    ),
    ("infrastructure/persistence/log_repositories.py", "AuditLogRepository"): (
        "Audit login: log sự kiện và truy vấn failed login.",
        ["audit", "repository", "login"],
        "moderate",
    ),
    ("infrastructure/persistence/map_repository.py", "MapVersionRepository"): (
        "Quản lý phiên bản file map đã import.",
        ["map", "repository", "versioning"],
        "moderate",
    ),
    ("infrastructure/persistence/map_repository.py", "MapStateRepository"): (
        "Lưu map version đang active (singleton state doc).",
        ["map", "repository", "state"],
        "simple",
    ),
    ("infrastructure/persistence/node_repository.py", "NodeRepository"): (
        "Toàn bộ thao tác node AMR: lock, priority, zone và camera mapping.",
        ["node", "dispatch", "repository"],
        "complex",
    ),
    ("infrastructure/persistence/notification_repository.py", "NotificationRepository"): (
        "CRUD thông báo người dùng với phân trang và unread count.",
        ["notification", "repository", "mongodb"],
        "moderate",
    ),
    ("infrastructure/persistence/pairs_repository.py", "PairsRepository"): (
        "Quản lý cặp dispatch enabled/disabled theo zone.",
        ["pair", "dispatch", "repository"],
        "moderate",
    ),
    ("infrastructure/persistence/refresh_token_repository.py", "RefreshTokenRepository"): (
        "replace_one refresh token và revoke theo user.",
        ["auth", "repository", "refresh-token"],
        "simple",
    ),
    ("infrastructure/persistence/snapshot_repository.py", "SnapshotRepository"): (
        "Lưu snapshot YOLO và thống kê false positive theo zone.",
        ["vision", "repository", "snapshot"],
        "moderate",
    ),
    ("infrastructure/persistence/user_repository.py", "UserRepository"): (
        "Truy cập collection users cho đăng nhập và quản trị.",
        ["auth", "repository", "user"],
        "simple",
    ),
    ("infrastructure/persistence/zone_repository.py", "ZoneRepository"): (
        "CRUD zone và kiểm tra cờ enabled.",
        ["zone", "repository", "mongodb"],
        "simple",
    ),
}

# Cross-batch call targets (callee name -> node id)
EXTERNAL_CALL_TARGETS = {
    "RuntimeService": "class:application/runtime/runtime_service.py:RuntimeService",
    "HttpOrderQuery": "class:infrastructure/ics/http_order_query.py:HttpOrderQuery",
    "setup_logger": "function:utils/setup_log.py:setup_logger",
    "settings": "config:config/settings.py",
    "permissions_for_role": "function:domain/permissions.py:permissions_for_role",
    "container": "class:application/container.py:AppContainer",
}

BATCH_CALL_MAP = {
    "connect": "function:infrastructure/persistence/db.py:connect",
    "disconnect": "function:infrastructure/persistence/db.py:disconnect",
    "ensure_auth_indexes": "function:infrastructure/auth/indexes.py:ensure_auth_indexes",
    "MongoHealthAdapter": "class:infrastructure/persistence/db_health.py:MongoHealthAdapter",
    "AuthAuditAdapter": "class:infrastructure/auth/audit_adapter.py:AuthAuditAdapter",
    "BcryptHasher": "class:infrastructure/auth/password_hasher.py:BcryptHasher",
    "JwtTokenService": "class:infrastructure/auth/jwt_service.py:JwtTokenService",
    "ActionAuditAdapter": "class:infrastructure/auth/action_audit_adapter.py:ActionAuditAdapter",
    "SystemActionAuditAdapter": "class:infrastructure/auth/system_action_audit_adapter.py:SystemActionAuditAdapter",
    "_read_password": "function:scripts/seed_users.py:_read_password",
    "_build_doc": "function:scripts/seed_users.py:_build_doc",
    "_perm_diff": "function:scripts/seed_users.py:_perm_diff",
    "_redact": "function:infrastructure/auth/action_audit_adapter.py:_redact",
    "get_db": "function:infrastructure/persistence/db.py:get_db",
    "get_collection": "function:infrastructure/persistence/db.py:get_collection",
    "_now": "function:infrastructure/persistence/base_repository.py:_now",
    "_serialize": "function:infrastructure/persistence/base_repository.py:_serialize",
}

nodes: list[dict] = []
edges: list[dict] = []
node_ids: set[str] = set()


def add_node(node: dict) -> None:
    if node["id"] in node_ids:
        return
    node_ids.add(node["id"])
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


for path in sorted(by_path.keys()):
    r = by_path[path]
    name = Path(path).name
    summary, tags, complexity, lang_notes = FILE_META.get(
        path,
        (
            f"Tệp mã nguồn {path}.",
            ["python", "code"],
            "simple",
            None,
        ),
    )
    file_node = {
        "id": f"file:{path}",
        "type": "file",
        "name": name,
        "filePath": path,
        "summary": summary,
        "tags": tags,
        "complexity": complexity,
    }
    if lang_notes:
        file_node["languageNotes"] = lang_notes
    add_node(file_node)

    exported = export_names.get(path, set())

    for fn in r.get("functions") or []:
        if not fn_significant(path, fn):
            continue
        fid = f"function:{path}:{fn['name']}"
        fs, ft, fc = FN_META.get(
            (path, fn["name"]),
            (
                f"Hàm {fn['name']} trong {name}.",
                ["python", "function"],
                "simple",
            ),
        )
        add_node(
            {
                "id": fid,
                "type": "function",
                "name": fn["name"],
                "filePath": path,
                "lineRange": [fn["startLine"], fn["endLine"]],
                "summary": fs,
                "tags": ft,
                "complexity": fc,
            }
        )
        add_edge(f"file:{path}", fid, "contains", 1.0)
        if fn["name"] in exported:
            add_edge(f"file:{path}", fid, "exports", 0.8)

    for cls in r.get("classes") or []:
        if not cls_significant(path, cls):
            continue
        cid = f"class:{path}:{cls['name']}"
        cs, ct, cc = CLS_META.get(
            (path, cls["name"]),
            (
                f"Lớp {cls['name']} trong {name}.",
                ["python", "class"],
                "moderate",
            ),
        )
        add_node(
            {
                "id": cid,
                "type": "class",
                "name": cls["name"],
                "filePath": path,
                "lineRange": [cls["startLine"], cls["endLine"]],
                "summary": cs,
                "tags": ct,
                "complexity": cc,
            }
        )
        add_edge(f"file:{path}", cid, "contains", 1.0)
        if cls["name"] in exported:
            add_edge(f"file:{path}", cid, "exports", 0.8)

# imports — exactly one per batchImportData entry
expected_imports = 0
for file_path, targets in batch_import.items():
    for target in targets:
        expected_imports += 1
        add_edge(f"file:{file_path}", f"file:{target}", "imports", 0.7)

# calls from callGraph
caller_to_file_fn: dict[str, tuple[str, str]] = {}
for path, r in by_path.items():
    for fn in r.get("functions") or []:
        if fn_significant(path, fn):
            caller_to_file_fn[fn["name"]] = (path, fn["name"])
    for cls in r.get("classes") or []:
        if cls_significant(path, cls):
            for m in cls.get("methods") or []:
                caller_to_file_fn[m] = (path, cls["name"])

seen_calls: set[tuple[str, str]] = set()

for path, r in by_path.items():
    for cg in r.get("callGraph") or []:
        caller = cg["caller"]
        callee = cg["callee"]
        if caller not in caller_to_file_fn and caller not in {
            m for c in r.get("classes") or [] for m in (c.get("methods") or [])
        }:
            # method on class: caller is method name
            if caller not in caller_to_file_fn:
                # resolve method -> class file
                for cls in r.get("classes") or []:
                    if caller in (cls.get("methods") or []):
                        caller_to_file_fn[caller] = (path, cls["name"])
                        break
        src_path, src_sym = caller_to_file_fn.get(caller, (None, None))
        if not src_path:
            continue
        if src_sym in export_names.get(src_path, set()) or any(
            f["name"] == src_sym for f in by_path[src_path].get("functions") or []
        ):
            src_id = f"function:{src_path}:{src_sym}"
        else:
            # method caller maps to class node id for cross-call edges
            src_id = f"class:{src_path}:{src_sym}"

        target_id = None
        bare = callee.split(".")[0].split("(")[0]
        if bare in BATCH_CALL_MAP:
            target_id = BATCH_CALL_MAP[bare]
        elif bare in EXTERNAL_CALL_TARGETS:
            target_id = EXTERNAL_CALL_TARGETS[bare]
        elif callee.endswith("()") and callee[:-2] in BATCH_CALL_MAP:
            target_id = BATCH_CALL_MAP[callee[:-2]]
        elif callee in BATCH_CALL_MAP:
            target_id = BATCH_CALL_MAP[callee]

        if not target_id:
            continue
        key = (src_id, target_id)
        if key in seen_calls:
            continue
        seen_calls.add(key)
        add_edge(src_id, target_id, "calls", 0.8)

# lifespan-specific cross-batch calls (explicit from app.py call graph)
lifespan_id = "function:app.py:lifespan"
for callee, tid in [
    ("connect", BATCH_CALL_MAP["connect"]),
    ("disconnect", BATCH_CALL_MAP["disconnect"]),
    ("ensure_auth_indexes", BATCH_CALL_MAP["ensure_auth_indexes"]),
    ("MongoHealthAdapter", BATCH_CALL_MAP["MongoHealthAdapter"]),
    ("AuthAuditAdapter", BATCH_CALL_MAP["AuthAuditAdapter"]),
    ("BcryptHasher", BATCH_CALL_MAP["BcryptHasher"]),
    ("JwtTokenService", BATCH_CALL_MAP["JwtTokenService"]),
    ("ActionAuditAdapter", BATCH_CALL_MAP["ActionAuditAdapter"]),
    ("SystemActionAuditAdapter", BATCH_CALL_MAP["SystemActionAuditAdapter"]),
    ("RuntimeService", EXTERNAL_CALL_TARGETS["RuntimeService"]),
]:
    key = (lifespan_id, tid)
    if key not in seen_calls:
        seen_calls.add(key)
        add_edge(lifespan_id, tid, "calls", 0.8)

main_id = "function:scripts/seed_users.py:main"
for tid in [
    BATCH_CALL_MAP["BcryptHasher"],
    BATCH_CALL_MAP["_read_password"],
    BATCH_CALL_MAP["_build_doc"],
    BATCH_CALL_MAP["_perm_diff"],
    EXTERNAL_CALL_TARGETS["permissions_for_role"],
]:
    key = (main_id, tid)
    if key not in seen_calls:
        seen_calls.add(key)
        add_edge(main_id, tid, "calls", 0.8)

log_id = "function:infrastructure/auth/action_audit_adapter.py:_redact"
for path, r in by_path.items():
    for cg in r.get("callGraph") or []:
        if cg["caller"] == "log" and cg["callee"] == "_redact":
            add_edge(
                "class:infrastructure/auth/action_audit_adapter.py:ActionAuditAdapter",
                log_id,
                "calls",
                0.8,
            )

out = {"nodes": nodes, "edges": edges}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
    f.write("\n")

actual_imports = sum(1 for e in edges if e["type"] == "imports")
print(f"nodes={len(nodes)}")
print(f"edges={len(edges)}")
print(f"imports_expected={expected_imports}")
print(f"imports_actual={actual_imports}")
