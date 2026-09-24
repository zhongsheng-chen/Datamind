"""认证异常定义.

统一定义登录、令牌校验和权限检查过程中的异常类型。

核心功能：
  - AuthError: 认证模块基础异常
  - AuthenticationRequiredError: 用户尚未认证
  - InvalidCredentialsError: 用户名或密码错误
  - UserDisabledError: 用户已停用
  - UserLockedError: 用户已锁定
  - TokenError: 令牌异常
  - InvalidAccessTokenError: 访问令牌无效
  - AccessTokenExpiredError: 访问令牌已过期
  - InvalidRefreshTokenError: 刷新令牌无效
  - RefreshTokenExpiredError: 刷新令牌已过期
  - RefreshTokenRevokedError: 刷新令牌已撤销
  - PermissionDeniedError: 用户权限不足

使用示例：
  from datamind.auth.errors import (
      InvalidCredentialsError,
      PermissionDeniedError,
      RefreshTokenRevokedError,
  )

  # 用户不存在或密码校验失败时统一抛出凭证错误
  raise InvalidCredentialsError()

  # 刷新令牌已被撤销时抛出令牌撤销异常
  raise RefreshTokenRevokedError()

  # 当前用户缺少所需权限时抛出权限不足异常
  raise PermissionDeniedError(
      "缺少模型删除权限"
  )
"""


class AuthError(Exception):
    """认证模块基础异常."""

    default_message = "认证失败"

    def __init__(
            self,
            message: str | None = None,
    ) -> None:
        """初始化认证异常.

        参数：
            message: 异常消息，默认使用当前异常类型的默认消息
        """
        resolved_message = (
            message
            if message is not None
            else self.default_message
        )

        super().__init__(
            resolved_message
        )

        self.message = resolved_message


class AuthenticationRequiredError(
    AuthError
):
    """用户尚未认证."""

    default_message = "用户尚未认证"


class InvalidCredentialsError(
    AuthError
):
    """用户名或密码错误."""

    default_message = "用户名或密码错误"


class UserDisabledError(
    AuthError
):
    """用户已停用."""

    default_message = "用户已停用"


class UserLockedError(
    AuthError
):
    """用户已锁定."""

    default_message = "用户已锁定"


class TokenError(
    AuthError
):
    """令牌异常."""

    default_message = "令牌无效"


class InvalidAccessTokenError(
    TokenError
):
    """访问令牌无效."""

    default_message = "访问令牌无效"


class AccessTokenExpiredError(
    TokenError
):
    """访问令牌已过期."""

    default_message = "访问令牌已过期"


class InvalidRefreshTokenError(
    TokenError
):
    """刷新令牌无效."""

    default_message = "刷新令牌无效"


class RefreshTokenExpiredError(
    TokenError
):
    """刷新令牌已过期."""

    default_message = "刷新令牌已过期"


class RefreshTokenRevokedError(
    TokenError
):
    """刷新令牌已撤销."""

    default_message = "刷新令牌已撤销"


class PermissionDeniedError(
    AuthError
):
    """用户权限不足."""

    default_message = "用户权限不足"


__all__ = [
    "AuthError",
    "AuthenticationRequiredError",
    "InvalidCredentialsError",
    "UserDisabledError",
    "UserLockedError",
    "TokenError",
    "InvalidAccessTokenError",
    "AccessTokenExpiredError",
    "InvalidRefreshTokenError",
    "RefreshTokenExpiredError",
    "RefreshTokenRevokedError",
    "PermissionDeniedError",
]
