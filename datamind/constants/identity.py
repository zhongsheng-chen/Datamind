"""身份管理常量

定义内置角色及其固定权限。

核心功能：
  - SYSTEM_BOOTSTRAP_ACTOR: 系统初始化操作人
  - ADMINISTRATOR_DISPLAY_NAME: 管理员默认显示名称
  - ADMINISTRATOR_ROLE_NAME: 管理员角色名称
  - ADMINISTRATOR_PERMISSIONS: 管理员角色权限
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


SYSTEM_BOOTSTRAP_ACTOR: Final[str] = "system:bootstrap"
ADMINISTRATOR_DISPLAY_NAME: Final[str] = "Administrator"
ADMINISTRATOR_ROLE_NAME: Final[str] = "administrator"
ADMINISTRATOR_PERMISSIONS: Final[tuple[str, ...]] = (
    "*",
)
BUILTIN_ROLE_NAMES: FrozenSet[str] = frozenset({
    ADMINISTRATOR_ROLE_NAME,
})
