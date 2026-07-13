# datamind/constants/identity.py

"""身份管理常量

定义内置角色及其固定权限。

核心功能：
  - SYSTEM_ADMIN_ROLE_NAME: 系统管理员角色名称
  - SYSTEM_ADMIN_PERMISSIONS: 系统管理员角色权限
  - BUILTIN_ROLE_NAMES: 内置角色名称集合

使用示例：
  from datamind.constants.identity import BUILTIN_ROLE_NAMES

  if role_name in BUILTIN_ROLE_NAMES:
      protect_builtin_role()
"""

from typing import (
    Final,
    FrozenSet,
)


SYSTEM_ADMIN_ROLE_NAME: Final[str] = "system-admin"
SYSTEM_ADMIN_PERMISSIONS: Final[tuple[str, ...]] = (
    "*",
)
BUILTIN_ROLE_NAMES: FrozenSet[str] = frozenset({
    SYSTEM_ADMIN_ROLE_NAME,
})
