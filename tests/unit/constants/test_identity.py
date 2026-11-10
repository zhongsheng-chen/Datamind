"""身份管理常量测试.

验证内置角色名称和固定权限定义。

核心功能：
  - test_administrator_role_definition:
    验证系统管理员角色名称和权限
  - test_builtin_role_names:
    验证内置角色名称、描述与固定权限定义的完整性
  - test_builtin_role_permission_boundaries:
    验证各内置角色的实际权限匹配范围
  - test_viewer_and_auditor_combine_read_permissions:
    验证查看者与审计员组合后覆盖全部只读权限
"""

import pytest

from datamind.auth.permissions import has_permission
from datamind.constants.identity import (
    ADMINISTRATOR_DISPLAY_NAME,
    ADMINISTRATOR_ROLE_NAME,
    BUILTIN_ROLE_DESCRIPTIONS,
    BUILTIN_ROLE_NAMES,
    BUILTIN_ROLE_PERMISSIONS,
    SYSTEM_BOOTSTRAP_ACTOR,
)
from datamind.constants.permissions import SUPPORTED_PERMISSIONS


def test_administrator_role_definition() -> None:
    """测试系统管理员角色具有全部权限."""
    assert ADMINISTRATOR_ROLE_NAME == "administrator"
    assert ADMINISTRATOR_DISPLAY_NAME == "Administrator"
    assert BUILTIN_ROLE_PERMISSIONS[ADMINISTRATOR_ROLE_NAME] == (
        "*",
    )
    assert SYSTEM_BOOTSTRAP_ACTOR == "system:bootstrap"


def test_builtin_role_names() -> None:
    """测试五个内置角色使用完整且有效的固定权限定义."""
    assert BUILTIN_ROLE_NAMES == frozenset({
        "administrator", "editor", "viewer", "invoker", "auditor",
    })
    assert set(BUILTIN_ROLE_DESCRIPTIONS) == BUILTIN_ROLE_NAMES

    for name, permissions in BUILTIN_ROLE_PERMISSIONS.items():
        assert permissions
        assert len(permissions) == len(set(permissions))
        assert set(permissions) <= SUPPORTED_PERMISSIONS | {"*"}
        assert name == "administrator" or "*" not in permissions


@pytest.mark.parametrize(
    "role, expected",
    [
        ("administrator", SUPPORTED_PERMISSIONS),
        (
            "editor",
            {
                "model.read", "model.write",
                "deployment.read", "deployment.write",
                "experiment.read", "experiment.write",
                "routing.read", "routing.write",
                "runtime.read", "runtime.manage", "prediction.invoke",
            },
        ),
        (
            "viewer",
            {
                "model.read", "deployment.read", "experiment.read",
                "routing.read", "runtime.read",
            },
        ),
        ("invoker", {"prediction.invoke"}),
        ("auditor", {"audit.read", "request.read", "identity.read"}),
    ],
)
def test_builtin_role_permission_boundaries(
        role: str,
        expected: set[str] | frozenset[str],
) -> None:
    """测试实际权限匹配不会为非管理员授予删除、导出或身份管理能力."""
    for permission in SUPPORTED_PERMISSIONS:
        assert has_permission(
            granted_permissions=BUILTIN_ROLE_PERMISSIONS[role],
            required_permission=permission,
        ) is (permission in expected)


def test_viewer_and_auditor_combine_read_permissions() -> None:
    """测试组合查看者和审计员可获得所有只读权限."""
    permissions = (
        *BUILTIN_ROLE_PERMISSIONS["viewer"],
        *BUILTIN_ROLE_PERMISSIONS["auditor"],
    )
    assert set(permissions) == {
        permission
        for permission in SUPPORTED_PERMISSIONS
        if permission.endswith(".read")
    }
