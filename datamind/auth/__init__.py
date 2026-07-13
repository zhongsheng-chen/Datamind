# datamind/auth/__init__.py

"""认证组件

提供认证服务、请求响应结构、认证枚举、标准异常和权限校验入口。

核心功能：
  - AuthService: 认证服务
  - create_auth_service: 创建认证服务
  - LoginRequest: 登录请求
  - RefreshTokenRequest: 刷新令牌请求
  - LogoutRequest: 退出登录请求
  - TokenResponse: 令牌响应
  - AccessTokenClaims: 访问令牌声明
  - AuthenticatedUser: 已认证用户信息
  - UserStatus: 用户状态枚举
  - AuthError: 认证模块基础异常
  - AuthenticationRequiredError: 未认证异常
  - InvalidCredentialsError: 无效凭证异常
  - UserDisabledError: 用户停用异常
  - UserLockedError: 用户锁定异常
  - TokenError: 令牌基础异常
  - InvalidAccessTokenError: 无效访问令牌异常
  - AccessTokenExpiredError: 访问令牌过期异常
  - InvalidRefreshTokenError: 无效刷新令牌异常
  - RefreshTokenExpiredError: 刷新令牌过期异常
  - RefreshTokenRevokedError: 刷新令牌撤销异常
  - PermissionDeniedError: 权限不足异常
  - normalize_permission: 规范化权限标识
  - permission_implies: 判断权限包含关系
  - has_permission: 检查单项权限
  - has_any_permission: 检查任一权限
  - has_all_permissions: 检查全部权限
  - require_permission: 要求单项权限
  - require_any_permission: 要求任一权限
  - require_all_permissions: 要求全部权限

使用示例：
  from datamind.auth import (
      LoginRequest,
      create_auth_service,
      require_permission,
  )

  auth_service = create_auth_service(
      session=session
  )

  token_response = await auth_service.login(
      LoginRequest(
          username="admin",
          password="P@ssw1rd",
      )
  )

  current_user = await auth_service.authenticate_access_token(
      token_response.access_token
  )

  require_permission(
      granted_permissions=current_user.permissions,
      required_permission="model.read",
  )
"""

from importlib import import_module
from typing import Any, Final


_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "AuthService": (
        "datamind.auth.service",
        "AuthService",
    ),
    "create_auth_service": (
        "datamind.auth.factory",
        "create_auth_service",
    ),
    "LoginRequest": (
        "datamind.auth.schemas",
        "LoginRequest",
    ),
    "RefreshTokenRequest": (
        "datamind.auth.schemas",
        "RefreshTokenRequest",
    ),
    "LogoutRequest": (
        "datamind.auth.schemas",
        "LogoutRequest",
    ),
    "TokenResponse": (
        "datamind.auth.schemas",
        "TokenResponse",
    ),
    "AccessTokenClaims": (
        "datamind.auth.schemas",
        "AccessTokenClaims",
    ),
    "AuthenticatedUser": (
        "datamind.auth.schemas",
        "AuthenticatedUser",
    ),
    "UserStatus": (
        "datamind.auth.enums",
        "UserStatus",
    ),
    "AuthError": (
        "datamind.auth.errors",
        "AuthError",
    ),
    "AuthenticationRequiredError": (
        "datamind.auth.errors",
        "AuthenticationRequiredError",
    ),
    "InvalidCredentialsError": (
        "datamind.auth.errors",
        "InvalidCredentialsError",
    ),
    "UserDisabledError": (
        "datamind.auth.errors",
        "UserDisabledError",
    ),
    "UserLockedError": (
        "datamind.auth.errors",
        "UserLockedError",
    ),
    "TokenError": (
        "datamind.auth.errors",
        "TokenError",
    ),
    "InvalidAccessTokenError": (
        "datamind.auth.errors",
        "InvalidAccessTokenError",
    ),
    "AccessTokenExpiredError": (
        "datamind.auth.errors",
        "AccessTokenExpiredError",
    ),
    "InvalidRefreshTokenError": (
        "datamind.auth.errors",
        "InvalidRefreshTokenError",
    ),
    "RefreshTokenExpiredError": (
        "datamind.auth.errors",
        "RefreshTokenExpiredError",
    ),
    "RefreshTokenRevokedError": (
        "datamind.auth.errors",
        "RefreshTokenRevokedError",
    ),
    "PermissionDeniedError": (
        "datamind.auth.errors",
        "PermissionDeniedError",
    ),
    "normalize_permission": (
        "datamind.auth.permissions",
        "normalize_permission",
    ),
    "permission_implies": (
        "datamind.auth.permissions",
        "permission_implies",
    ),
    "has_permission": (
        "datamind.auth.permissions",
        "has_permission",
    ),
    "has_any_permission": (
        "datamind.auth.permissions",
        "has_any_permission",
    ),
    "has_all_permissions": (
        "datamind.auth.permissions",
        "has_all_permissions",
    ),
    "require_permission": (
        "datamind.auth.permissions",
        "require_permission",
    ),
    "require_any_permission": (
        "datamind.auth.permissions",
        "require_any_permission",
    ),
    "require_all_permissions": (
        "datamind.auth.permissions",
        "require_all_permissions",
    ),
}

__all__ = list(
    _EXPORTS
)


def __getattr__(
        name: str,
) -> Any:
    """按需加载包级公共对象"""
    export = _EXPORTS.get(
        name
    )

    if export is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    module_name, attribute_name = export
    value = getattr(
        import_module(
            module_name
        ),
        attribute_name,
    )
    globals()[name] = value

    return value


def __dir__() -> list[str]:
    """返回包含延迟公共导出的模块属性列表"""
    return sorted({
        *globals(),
        *__all__,
    })
