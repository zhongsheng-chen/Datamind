"""身份管理常量测试.

验证内置角色名称和固定权限定义。

核心功能：
  - test_administrator_role_definition:
    验证系统管理员角色名称和权限
  - test_builtin_role_names_contains_only_administrator:
    验证仅内置系统管理员角色
"""

from datamind.constants.identity import (
    ADMINISTRATOR_DISPLAY_NAME,
    ADMINISTRATOR_PERMISSIONS,
    ADMINISTRATOR_ROLE_NAME,
    BUILTIN_ROLE_NAMES,
    SYSTEM_BOOTSTRAP_ACTOR,
)


def test_administrator_role_definition() -> None:
    """测试系统管理员角色具有全部权限."""
    assert ADMINISTRATOR_ROLE_NAME == "administrator"
    assert ADMINISTRATOR_DISPLAY_NAME == "Administrator"
    assert ADMINISTRATOR_PERMISSIONS == (
        "*",
    )
    assert SYSTEM_BOOTSTRAP_ACTOR == "system:bootstrap"


def test_builtin_role_names_contains_only_administrator() -> None:
    """测试内置角色仅包含系统管理员角色."""
    assert BUILTIN_ROLE_NAMES == frozenset({
        ADMINISTRATOR_ROLE_NAME,
    })
