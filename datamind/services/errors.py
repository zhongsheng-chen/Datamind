# datamind/services/errors.py

"""业务服务异常定义

统一定义业务服务使用的异常类型。

核心功能：
  - InitializationError: 系统初始化异常
  - AlreadyInitializedError: 系统已初始化异常
  - IdentityError: 身份管理基础异常
  - IdentityConflictError: 身份状态冲突异常
  - UserNotFoundError: 用户不存在异常
  - RoleNotFoundError: 角色不存在异常

使用示例：
  from datamind.services.errors import (
      IdentityConflictError,
      UserNotFoundError,
  )

  if user is None:
      raise UserNotFoundError(
          "用户不存在: alice"
      )

  if username_exists:
      raise IdentityConflictError(
          "用户名已存在: alice"
      )
"""


class InitializationError(Exception):
    """系统初始化异常"""


class AlreadyInitializedError(
    InitializationError
):
    """系统已经完成初始化"""


class IdentityError(Exception):
    """身份管理基础异常"""


class IdentityConflictError(
    IdentityError
):
    """身份状态冲突异常"""


class UserNotFoundError(
    IdentityError
):
    """用户不存在异常"""


class RoleNotFoundError(
    IdentityError
):
    """角色不存在异常"""


__all__ = [
    "InitializationError",
    "AlreadyInitializedError",
    "IdentityError",
    "IdentityConflictError",
    "UserNotFoundError",
    "RoleNotFoundError",
]
