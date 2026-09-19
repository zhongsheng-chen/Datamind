"""权限校验工具测试

验证权限标识规范化、精确权限匹配、通配符匹配、
批量权限检查和权限不足异常处理。

核心功能：
  - test_normalize_permission_strips_whitespace:
    验证去除权限标识首尾空白
  - test_normalize_permission_rejects_empty_permission:
    验证拒绝空权限标识
  - test_permission_implies_matches_permissions:
    验证全局、精确和命名空间权限匹配
  - test_permission_implies_rejects_unmatched_permissions:
    验证不同命名空间和大小写不匹配
  - test_has_permission_checks_granted_permissions:
    验证单项权限检查
  - test_has_any_permission_checks_required_permissions:
    验证任一权限检查
  - test_has_all_permissions_checks_required_permissions:
    验证全部权限检查
  - test_require_permission_allows_matching_permission:
    验证单项权限满足时不抛出异常
  - test_require_permission_rejects_missing_permission:
    验证缺少单项权限时抛出异常
  - test_require_any_permission_validates_permissions:
    验证任一权限要求和空集合校验
  - test_require_all_permissions_validates_permissions:
    验证全部权限要求、缺失权限和空集合校验
  - test_required_permissions_are_normalized_and_deduplicated:
    验证批量目标权限规范化和去重
"""

from collections.abc import (
    Callable,
    Iterable,
)

import pytest

from datamind.auth.errors import PermissionDeniedError
from datamind.auth.permissions import (
    has_all_permissions,
    has_any_permission,
    has_permission,
    normalize_permission,
    permission_implies,
    require_all_permissions,
    require_any_permission,
    require_permission,
)


def test_normalize_permission_strips_whitespace() -> None:
    """测试去除权限标识首尾空白"""
    result = normalize_permission(
        "  model.read  "
    )

    assert result == "model.read"


@pytest.mark.parametrize(
    "permission",
    [
        "",
        " ",
        "\t",
        "\n",
        " \t\n ",
    ],
)
def test_normalize_permission_rejects_empty_permission(
        permission: str,
) -> None:
    """测试拒绝空权限标识"""
    with pytest.raises(
            ValueError,
            match="permission 不能为空",
    ):
        normalize_permission(
            permission
        )


@pytest.mark.parametrize(
    (
        "granted_permission",
        "required_permission",
    ),
    [
        (
            "*",
            "model.delete",
        ),
        (
            "*",
            "experiment.read",
        ),
        (
            "model.read",
            "model.read",
        ),
        (
            " model.read ",
            "model.read",
        ),
        (
            "model.*",
            "model.read",
        ),
        (
            "model.*",
            "model.version.delete",
        ),
        (
            " model.* ",
            " model.update ",
        ),
    ],
)
def test_permission_implies_matches_permissions(
        granted_permission: str,
        required_permission: str,
) -> None:
    """测试全局、精确和命名空间权限匹配"""
    result = permission_implies(
        granted_permission=granted_permission,
        required_permission=required_permission,
    )

    assert result is True


@pytest.mark.parametrize(
    (
        "granted_permission",
        "required_permission",
    ),
    [
        (
            "model.read",
            "model.write",
        ),
        (
            "model.*",
            "deployment.read",
        ),
        (
            "model.*",
            "modeling.read",
        ),
        (
            "model.read",
            "model.read.detail",
        ),
        (
            "model.*",
            "Model.read",
        ),
        (
            "MODEL.*",
            "model.read",
        ),
    ],
)
def test_permission_implies_rejects_unmatched_permissions(
        granted_permission: str,
        required_permission: str,
) -> None:
    """测试不同命名空间和大小写不匹配"""
    result = permission_implies(
        granted_permission=granted_permission,
        required_permission=required_permission,
    )

    assert result is False


@pytest.mark.parametrize(
    (
        "granted_permissions",
        "required_permission",
        "expected",
    ),
    [
        (
            [
                "model.read",
                "experiment.read",
            ],
            "model.read",
            True,
        ),
        (
            [
                "model.*",
                "experiment.read",
            ],
            "model.version.delete",
            True,
        ),
        (
            [
                "*"
            ],
            "deployment.delete",
            True,
        ),
        (
            [],
            "model.read",
            False,
        ),
        (
            [
                "experiment.read"
            ],
            "model.read",
            False,
        ),
    ],
)
def test_has_permission_checks_granted_permissions(
        granted_permissions: list[str],
        required_permission: str,
        expected: bool,
) -> None:
    """测试单项权限检查"""
    result = has_permission(
        granted_permissions=granted_permissions,
        required_permission=required_permission,
    )

    assert result is expected


def test_has_permission_accepts_generator() -> None:
    """测试单项权限检查支持生成器"""
    granted_permissions = (
        permission
        for permission in [
            "experiment.read",
            "model.*",
        ]
    )

    result = has_permission(
        granted_permissions=granted_permissions,
        required_permission="model.delete",
    )

    assert result is True


@pytest.mark.parametrize(
    (
        "granted_permissions",
        "required_permissions",
        "expected",
    ),
    [
        (
            [
                "model.read",
                "experiment.read",
            ],
            [
                "deployment.read",
                "experiment.read",
            ],
            True,
        ),
        (
            [
                "model.*"
            ],
            [
                "model.delete",
                "deployment.read",
            ],
            True,
        ),
        (
            [
                "model.read"
            ],
            [
                "model.write",
                "experiment.read",
            ],
            False,
        ),
        (
            [],
            [
                "model.read"
            ],
            False,
        ),
        (
            [
                "model.read"
            ],
            [],
            False,
        ),
    ],
)
def test_has_any_permission_checks_required_permissions(
        granted_permissions: list[str],
        required_permissions: list[str],
        expected: bool,
) -> None:
    """测试任一权限检查"""
    result = has_any_permission(
        granted_permissions=granted_permissions,
        required_permissions=required_permissions,
    )

    assert result is expected


def test_has_any_permission_accepts_generators() -> None:
    """测试任一权限检查支持生成器"""
    granted_permissions = (
        permission
        for permission in [
            "model.read",
            "experiment.read",
        ]
    )
    required_permissions = (
        permission
        for permission in [
            "deployment.read",
            "experiment.read",
        ]
    )

    result = has_any_permission(
        granted_permissions=granted_permissions,
        required_permissions=required_permissions,
    )

    assert result is True


@pytest.mark.parametrize(
    (
        "granted_permissions",
        "required_permissions",
        "expected",
    ),
    [
        (
            [
                "model.read",
                "model.write",
            ],
            [
                "model.read",
                "model.write",
            ],
            True,
        ),
        (
            [
                "model.*"
            ],
            [
                "model.read",
                "model.version.delete",
            ],
            True,
        ),
        (
            [
                "*"
            ],
            [
                "model.read",
                "deployment.delete",
            ],
            True,
        ),
        (
            [
                "model.read"
            ],
            [
                "model.read",
                "model.write",
            ],
            False,
        ),
        (
            [],
            [
                "model.read"
            ],
            False,
        ),
        (
            [],
            [],
            True,
        ),
    ],
)
def test_has_all_permissions_checks_required_permissions(
        granted_permissions: list[str],
        required_permissions: list[str],
        expected: bool,
) -> None:
    """测试全部权限检查"""
    result = has_all_permissions(
        granted_permissions=granted_permissions,
        required_permissions=required_permissions,
    )

    assert result is expected


def test_has_all_permissions_accepts_generators() -> None:
    """测试全部权限检查支持生成器"""
    granted_permissions = (
        permission
        for permission in [
            "model.*",
            "experiment.read",
        ]
    )
    required_permissions = (
        permission
        for permission in [
            "model.read",
            "model.delete",
            "experiment.read",
        ]
    )

    result = has_all_permissions(
        granted_permissions=granted_permissions,
        required_permissions=required_permissions,
    )

    assert result is True


@pytest.mark.parametrize(
    (
        "granted_permissions",
        "required_permission",
    ),
    [
        (
            [
                "model.read"
            ],
            "model.read",
        ),
        (
            [
                "model.*"
            ],
            "model.delete",
        ),
        (
            [
                "*"
            ],
            "deployment.delete",
        ),
    ],
)
def test_require_permission_allows_matching_permission(
        granted_permissions: list[str],
        required_permission: str,
) -> None:
    """测试单项权限满足时不抛出异常"""
    require_permission(
        granted_permissions=granted_permissions,
        required_permission=required_permission,
    )


def test_require_permission_rejects_missing_permission() -> None:
    """测试缺少单项权限时抛出异常"""
    with pytest.raises(
            PermissionDeniedError,
            match="缺少权限: model.delete",
    ):
        require_permission(
            granted_permissions=[
                "model.read"
            ],
            required_permission=" model.delete ",
        )


def test_require_permission_rejects_empty_required_permission() -> None:
    """测试拒绝空的单项目标权限"""
    with pytest.raises(
            ValueError,
            match="permission 不能为空",
    ):
        require_permission(
            granted_permissions=[
                "model.read"
            ],
            required_permission=" ",
        )


def test_require_any_permission_allows_matching_permission() -> None:
    """测试拥有任一目标权限时不抛出异常"""
    require_any_permission(
        granted_permissions=[
            "model.*",
            "experiment.read",
        ],
        required_permissions=[
            "deployment.read",
            "model.delete",
        ],
    )


def test_require_any_permission_rejects_missing_permissions() -> None:
    """测试缺少全部候选权限时抛出异常"""
    with pytest.raises(
            PermissionDeniedError,
            match=(
                "缺少任一权限: "
                "deployment.read, experiment.write"
            ),
    ):
        require_any_permission(
            granted_permissions=[
                "model.read"
            ],
            required_permissions=[
                " deployment.read ",
                "experiment.write",
            ],
        )


@pytest.mark.parametrize(
    "required_permissions",
    [
        [],
        (),
    ],
)
def test_require_any_permission_rejects_empty_permissions(
        required_permissions: Iterable[str],
) -> None:
    """测试任一权限要求拒绝空集合"""
    with pytest.raises(
            ValueError,
            match="required_permissions 不能为空",
    ):
        require_any_permission(
            granted_permissions=[
                "model.read"
            ],
            required_permissions=required_permissions,
        )


def test_require_all_permissions_allows_matching_permissions() -> None:
    """测试拥有全部目标权限时不抛出异常"""
    require_all_permissions(
        granted_permissions=[
            "model.*",
            "experiment.read",
        ],
        required_permissions=[
            "model.read",
            "model.delete",
            "experiment.read",
        ],
    )


def test_require_all_permissions_reports_only_missing_permissions() -> None:
    """测试仅报告缺失的目标权限"""
    with pytest.raises(
            PermissionDeniedError,
            match=(
                "缺少权限: "
                "model.write, deployment.read"
            ),
    ):
        require_all_permissions(
            granted_permissions=[
                "model.read",
                "experiment.read",
            ],
            required_permissions=[
                "model.read",
                "model.write",
                "experiment.read",
                "deployment.read",
            ],
        )


@pytest.mark.parametrize(
    "required_permissions",
    [
        [],
        (),
    ],
)
def test_require_all_permissions_rejects_empty_permissions(
        required_permissions: Iterable[str],
) -> None:
    """测试全部权限要求拒绝空集合"""
    with pytest.raises(
            ValueError,
            match="required_permissions 不能为空",
    ):
        require_all_permissions(
            granted_permissions=[
                "model.read"
            ],
            required_permissions=required_permissions,
        )


def test_required_permissions_are_normalized_and_deduplicated() -> None:
    """测试批量目标权限规范化和去重"""
    with pytest.raises(
            PermissionDeniedError,
            match=(
                "缺少权限: "
                "model.write, deployment.read"
            ),
    ):
        require_all_permissions(
            granted_permissions=[
                "model.read"
            ],
            required_permissions=[
                " model.write ",
                "model.write",
                "deployment.read",
                " deployment.read ",
            ],
        )


@pytest.mark.parametrize(
    "require_function",
    [
        require_any_permission,
        require_all_permissions,
    ],
)
def test_batch_require_rejects_blank_permission(
        require_function: Callable[..., None],
) -> None:
    """测试批量权限要求拒绝空白权限标识"""
    with pytest.raises(
            ValueError,
            match="permission 不能为空",
    ):
        require_function(
            granted_permissions=[
                "model.read"
            ],
            required_permissions=[
                "model.read",
                " ",
            ],
        )
