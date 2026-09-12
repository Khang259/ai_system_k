"""Mapping role → permissions. Nguồn duy nhất cho seed script + tài liệu API."""
from domain.permissions import (
    ALL_PERMISSIONS,
    CAMERA_READ,
    CAMERA_WRITE,
    MAP_READ,
    MAP_WRITE,
    SYSTEM_CONTROL,
    permissions_for_role,
)


def test_admin_has_every_permission():
    assert set(permissions_for_role("admin")) == set(ALL_PERMISSIONS)


def test_operator_can_write_camera_but_not_control_system():
    perms = permissions_for_role("operator")
    assert CAMERA_WRITE in perms
    assert SYSTEM_CONTROL not in perms
    assert MAP_READ in perms
    assert MAP_WRITE not in perms


def test_viewer_is_read_only():
    perms = permissions_for_role("viewer")
    assert CAMERA_READ in perms
    assert CAMERA_WRITE not in perms
    assert MAP_READ in perms
    assert MAP_WRITE not in perms


def test_unknown_role_gets_nothing():
    """Mặc định an toàn: role lạ không có quyền nào."""
    assert permissions_for_role("giam-doc") == []
    assert permissions_for_role("") == []
    assert permissions_for_role(None) == []


def test_role_lookup_ignores_case_and_spaces():
    assert permissions_for_role("  ADMIN ") == permissions_for_role("admin")


def test_returns_copy_so_caller_cannot_mutate_source():
    perms = permissions_for_role("viewer")
    perms.append("hacked")
    assert "hacked" not in permissions_for_role("viewer")


def test_no_command_permission_yet():
    """`send_command` đang hoãn — chưa có quyền nào cho nó."""
    assert not any(p.startswith("node.command") for p in ALL_PERMISSIONS)
