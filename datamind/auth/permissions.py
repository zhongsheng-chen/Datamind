# datamind/auth/permissions.py

"""权限校验工具

提供权限标识规范化、单项权限匹配和批量权限检查能力。

核心功能：
  - normalize_permission: 规范化权限标识
  - permission_implies: 判断已授予权限是否包含目标权限
  - has_permission: 检查是否拥有指定权限
  - has_any_permission: 检查是否拥有任一指定权限
  - has_all_permissions: 检查是否拥有全部指定权限
  - require_permission: 要求拥有指定权限
  - require_any_permission: 要求拥有任一指定权限
  - require_all_permissions: 要求拥有全部指定权限

使用示例：
  from datamind.auth.permissions import (
      has_all_permissions,
      has_any_permission,
      has_permission,
      require_permission,
  )

  granted_permissions = [
      "model.*",
      "experiment.read",
  ]

  # 检查是否拥有单项权限
  can_delete_model = has_permission(
      granted_permissions=granted_permissions,
      required_permission="model.delete",
  )

  # 检查是否拥有任一指定权限
  can_view_resource = has_any_permission(
      granted_permissions=granted_permissions,
      required_permissions=[
          "deployment.read",
          "experiment.read",
      ],
  )

  # 检查是否拥有全部指定权限
  can_manage_model = has_all_permissions(
      granted_permissions=granted_permissions,
      required_permissions=[
          "model.read",
          "model.update",
      ],
  )

  # 权限不足时抛出 PermissionDeniedError
  require_permission(
      granted_permissions=granted_permissions,
      required_permission="model.delete",
  )
"""

from collections.abc import Iterable

from datamind.auth.errors import PermissionDeniedError


def normalize_permission(
        permission: str,
) -> str:
    """规范化权限标识

    参数：
        permission: 权限标识

    返回：
        去除首尾空白后的权限标识

    异常：
        ValueError: permission 为空
    """
    normalized = permission.strip()

    if normalized == "":
        raise ValueError(
            "permission 不能为空"
        )

    return normalized


def permission_implies(
        *,
        granted_permission: str,
        required_permission: str,
) -> bool:
    """判断已授予权限是否包含目标权限

    参数：
        granted_permission: 已授予权限
        required_permission: 目标权限

    返回：
        True 表示已授予权限包含目标权限，否则返回 False
    """
    granted = normalize_permission(
        granted_permission
    )
    required = normalize_permission(
        required_permission
    )

    if granted == "*":
        return True

    if granted == required:
        return True

    if not granted.endswith(
            ".*"
    ):
        return False

    namespace_prefix = granted[:-1]

    return required.startswith(
        namespace_prefix
    )


def has_permission(
        *,
        granted_permissions: Iterable[str],
        required_permission: str,
) -> bool:
    """检查是否拥有指定权限

    参数：
        granted_permissions: 已授予权限集合
        required_permission: 目标权限

    返回：
        True 表示拥有指定权限，否则返回 False
    """
    required = normalize_permission(
        required_permission
    )

    return any(
        permission_implies(
            granted_permission=granted,
            required_permission=required,
        )
        for granted in granted_permissions
    )


def has_any_permission(
        *,
        granted_permissions: Iterable[str],
        required_permissions: Iterable[str],
) -> bool:
    """检查是否拥有任一指定权限

    参数：
        granted_permissions: 已授予权限集合
        required_permissions: 目标权限集合

    返回：
        True 表示至少拥有一项指定权限，否则返回 False
    """
    granted = tuple(
        granted_permissions
    )

    return any(
        has_permission(
            granted_permissions=granted,
            required_permission=required,
        )
        for required in required_permissions
    )


def has_all_permissions(
        *,
        granted_permissions: Iterable[str],
        required_permissions: Iterable[str],
) -> bool:
    """检查是否拥有全部指定权限

    参数：
        granted_permissions: 已授予权限集合
        required_permissions: 目标权限集合

    返回：
        True 表示拥有全部指定权限，否则返回 False

    说明：
        required_permissions 为空时返回 True。
    """
    granted = tuple(
        granted_permissions
    )

    return all(
        has_permission(
            granted_permissions=granted,
            required_permission=required,
        )
        for required in required_permissions
    )


def require_permission(
        *,
        granted_permissions: Iterable[str],
        required_permission: str,
) -> None:
    """要求拥有指定权限

    参数：
        granted_permissions: 已授予权限集合
        required_permission: 目标权限

    异常：
        PermissionDeniedError: 未拥有目标权限
    """
    required = normalize_permission(
        required_permission
    )

    if has_permission(
            granted_permissions=granted_permissions,
            required_permission=required,
    ):
        return

    raise PermissionDeniedError(
        f"缺少权限: {required}"
    )


def require_any_permission(
        *,
        granted_permissions: Iterable[str],
        required_permissions: Iterable[str],
) -> None:
    """要求拥有任一指定权限

    参数：
        granted_permissions: 已授予权限集合
        required_permissions: 目标权限集合

    异常：
        ValueError: required_permissions 为空
        PermissionDeniedError: 未拥有任一目标权限
    """
    required = _normalize_permissions(
        required_permissions
    )

    if not required:
        raise ValueError(
            "required_permissions 不能为空"
        )

    if has_any_permission(
            granted_permissions=granted_permissions,
            required_permissions=required,
    ):
        return

    raise PermissionDeniedError(
        "缺少任一权限: "
        + ", ".join(
            required
        )
    )


def require_all_permissions(
        *,
        granted_permissions: Iterable[str],
        required_permissions: Iterable[str],
) -> None:
    """要求拥有全部指定权限

    参数：
        granted_permissions: 已授予权限集合
        required_permissions: 目标权限集合

    异常：
        ValueError: required_permissions 为空
        PermissionDeniedError: 未拥有全部目标权限
    """
    required = _normalize_permissions(
        required_permissions
    )

    if not required:
        raise ValueError(
            "required_permissions 不能为空"
        )

    missing_permissions = [
        permission
        for permission in required
        if not has_permission(
            granted_permissions=granted_permissions,
            required_permission=permission,
        )
    ]

    if not missing_permissions:
        return

    raise PermissionDeniedError(
        "缺少权限: "
        + ", ".join(
            missing_permissions
        )
    )


def _normalize_permissions(
        permissions: Iterable[str],
) -> tuple[str, ...]:
    """规范化权限集合"""
    return tuple(
        dict.fromkeys(
            normalize_permission(
                permission
            )
            for permission in permissions
        )
    )


__all__ = [
    "normalize_permission",
    "permission_implies",
    "has_permission",
    "has_any_permission",
    "has_all_permissions",
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
]
