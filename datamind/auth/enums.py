# datamind/auth/enums.py

"""认证枚举常量

统一定义认证模块使用的用户状态、角色状态、
角色授予状态和刷新令牌状态枚举。

核心功能：
  - UserStatus: 用户状态
  - RoleStatus: 角色状态
  - GrantStatus: 角色授予状态
  - TokenStatus: 刷新令牌状态

使用示例：
  from datamind.auth.enums import (
      GrantStatus,
      RoleStatus,
      TokenStatus,
      UserStatus,
  )

  # 创建用户状态枚举
  user_status = UserStatus(
      "active"
  )

  # 创建角色状态枚举
  role_status = RoleStatus(
      "active"
  )

  # 创建角色授予状态枚举
  grant_status = GrantStatus(
      "active"
  )

  # 创建刷新令牌状态枚举
  token_status = TokenStatus(
      "active"
  )
"""

from enum import Enum


class BaseEnum(
    str,
    Enum,
):
    """字符串枚举基类"""

    def __str__(
            self,
    ) -> str:
        """返回枚举字符串值"""
        return self.value


class UserStatus(
    BaseEnum
):
    """用户状态"""

    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class RoleStatus(
    BaseEnum
):
    """角色状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"


class GrantStatus(
    BaseEnum
):
    """角色授予状态"""

    ACTIVE = "active"
    REVOKED = "revoked"


class TokenStatus(
    BaseEnum
):
    """刷新令牌状态"""

    ACTIVE = "active"
    REVOKED = "revoked"


__all__ = [
    "BaseEnum",
    "UserStatus",
    "RoleStatus",
    "GrantStatus",
    "TokenStatus",
]
