# tests/constants/test_permissions.py

"""权限常量测试

验证 Datamind 公开权限注册表的完整性和不可变性。

核心功能：
  - test_supported_permissions_contains_public_permissions:
    验证权限注册表包含全部公开权限
  - test_supported_permissions_is_immutable:
    验证权限注册表不可变
"""

from datamind.constants.permissions import SUPPORTED_PERMISSIONS


EXPECTED_PERMISSIONS = {
    "model.read",
    "model.write",
    "model.delete",
    "deployment.read",
    "deployment.write",
    "experiment.read",
    "experiment.write",
    "identity.read",
    "identity.manage",
    "routing.read",
    "routing.write",
    "runtime.read",
    "runtime.manage",
    "outcome.write",
    "prediction.invoke",
    "request.read",
    "audit.read",
}


def test_supported_permissions_contains_public_permissions() -> None:
    """测试权限注册表包含全部公开权限"""
    assert SUPPORTED_PERMISSIONS == EXPECTED_PERMISSIONS


def test_supported_permissions_is_immutable() -> None:
    """测试权限注册表不可变"""
    assert isinstance(
        SUPPORTED_PERMISSIONS,
        frozenset,
    )
