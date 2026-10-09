"""权限常量.

定义角色授权和访问控制使用的权限标识。

核心功能：
  - SUPPORTED_PERMISSIONS: 支持的权限集合

使用示例：
  from datamind.constants.permissions import SUPPORTED_PERMISSIONS

  if permission not in SUPPORTED_PERMISSIONS:
      reject_permission(permission)
"""

from typing import FrozenSet


SUPPORTED_PERMISSIONS: FrozenSet[str] = frozenset({
    "model.read",
    "model.write",
    "model.delete",
    "deployment.read",
    "deployment.write",
    "deployment.delete",
    "experiment.read",
    "experiment.write",
    "experiment.delete",
    "identity.read",
    "identity.manage",
    "routing.read",
    "routing.write",
    "routing.delete",
    "runtime.read",
    "runtime.manage",
    "prediction.invoke",
    "request.read",
    "audit.read",
    "data.export",
})
