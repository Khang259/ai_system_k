"""
Danh sách quyền + mapping role → quyền.

Pure Python, không framework. Là **nguồn duy nhất** cho seed script và tài liệu
API; frontend kiểm tra theo mảng `permissions` trả về trong token, không theo role.

Thêm quyền mới: khai báo hằng số ở đây, gắn vào role, rồi cập nhật user trong
Mongo (token cũ chỉ nhận quyền mới sau khi hết hạn).
"""

CAMERA_READ = "camera.read"
CAMERA_WRITE = "camera.write"
NODE_READ = "node.read"
NODE_MAINTENANCE = "node.maintenance"
PAIR_WRITE = "pair.write"
ZONE_CONTROL = "zone.control"
SYSTEM_CONTROL = "system.control"
LOGS_READ = "logs.read"
MAP_READ = "map.read"
MAP_WRITE = "map.write"

ALL_PERMISSIONS = [
    CAMERA_READ,
    CAMERA_WRITE,
    NODE_READ,
    NODE_MAINTENANCE,
    PAIR_WRITE,
    ZONE_CONTROL,
    SYSTEM_CONTROL,
    LOGS_READ,
    MAP_READ,
    MAP_WRITE,
]

# Chưa có `node.command`: gửi lệnh thủ công đang hoãn (xem docs/api-fe-integration.md)
ROLE_PERMISSIONS = {
    "admin": list(ALL_PERMISSIONS),
    "operator": [
        CAMERA_READ,
        CAMERA_WRITE,
        NODE_READ,
        NODE_MAINTENANCE,
        ZONE_CONTROL,
        LOGS_READ,
        MAP_READ,
    ],
    "viewer": [
        CAMERA_READ,
        NODE_READ,
        LOGS_READ,
        MAP_READ,
    ],
}


def permissions_for_role(role: str) -> list:
    """Role lạ → không có quyền nào (mặc định an toàn)."""
    return list(ROLE_PERMISSIONS.get((role or "").lower().strip(), []))
