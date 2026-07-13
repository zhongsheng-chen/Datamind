# tests/constants/test_identity.py

"""身份管理常量测试

验证内置角色名称和固定权限定义。

核心功能：
  - test_system_admin_role_definition:
    验证系统管理员角色名称和权限
  - test_builtin_role_names_contains_only_system_admin:
    验证仅内置系统管理员角色
"""

from datamind.constants.identity import (
    BUILTIN_ROLE_NAMES,
    SYSTEM_ADMIN_PERMISSIONS,
    SYSTEM_ADMIN_ROLE_NAME,
)


def test_system_admin_role_definition() -> None:
    """测试系统管理员角色具有全部权限"""
    assert SYSTEM_ADMIN_ROLE_NAME == "system-admin"
    assert SYSTEM_ADMIN_PERMISSIONS == (
        "*",
    )


def test_builtin_role_names_contains_only_system_admin() -> None:
    """测试内置角色仅包含系统管理员角色"""
    assert BUILTIN_ROLE_NAMES == frozenset({
        SYSTEM_ADMIN_ROLE_NAME,
    })
