"""认证数据结构

提供认证流程使用的请求、响应和令牌声明数据结构。

核心功能：
  - LoginRequest: 登录请求
  - RefreshTokenRequest: 刷新访问令牌请求
  - LogoutRequest: 退出登录请求
  - LogoutResult: 退出登录结果
  - TokenResponse: 令牌响应
  - AccessTokenClaims: 访问令牌声明
  - AuthenticatedUser: 已认证用户信息

使用示例：
  from datamind.auth.enums import UserStatus
  from datamind.auth.schemas import (
      AccessTokenClaims,
      AuthenticatedUser,
      LoginRequest,
      LogoutRequest,
      LogoutResult,
      RefreshTokenRequest,
      TokenResponse,
  )

  # 构造登录请求
  login_request = LoginRequest(
      username="admin",
      password="P@ssw1rd",
  )

  # 获取登录请求中的原始密码
  password = login_request.password.get_secret_value()

  # 构造访问令牌和刷新令牌响应
  token_response = TokenResponse(
      access_token="access-token",
      refresh_token="refresh-token",
      expires_in=1800,
  )

  # 构造刷新访问令牌请求
  refresh_request = RefreshTokenRequest(
      refresh_token="refresh-token",
  )

  # 构造退出登录请求
  logout_request = LogoutRequest(
      refresh_token="refresh-token",
  )

  # 校验访问令牌声明
  token_claims = AccessTokenClaims(
      sub="usr_0123456789abcdef",
      type="access",
      iat=1785033600,
      exp=1785035400,
      username="admin",
      roles=["admin"],
      permissions=["model.*"],
  )

  # 构造已认证用户信息
  current_user = AuthenticatedUser(
      user_id=token_claims.sub,
      username="admin",
      display_name="Administrator",
      email="admin@example.com",
      status=UserStatus.ACTIVE,
      roles=token_claims.roles,
      permissions=token_claims.permissions,
  )
"""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
)

from datamind.auth.enums import UserStatus


class AuthSchema(
    BaseModel
):
    """认证数据结构基类"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class LoginRequest(
    AuthSchema
):
    """登录请求"""

    username: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="登录用户名",
    )

    password: SecretStr = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="登录密码",
    )


class RefreshTokenRequest(
    AuthSchema
):
    """刷新访问令牌请求"""

    refresh_token: SecretStr = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="刷新令牌",
    )


class LogoutRequest(
    AuthSchema
):
    """退出登录请求"""

    refresh_token: SecretStr = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="需要撤销的刷新令牌",
    )


class LogoutResult(
    AuthSchema
):
    """退出登录结果"""

    revoked: bool = Field(
        ...,
        description="本次是否撤销了有效刷新令牌",
    )

    user_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="刷新令牌所属用户 ID",
    )

    username: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="刷新令牌所属用户名",
    )


class TokenResponse(
    AuthSchema
):
    """令牌响应"""

    access_token: str = Field(
        ...,
        min_length=1,
        description="JWT 访问令牌",
    )

    refresh_token: str | None = Field(
        default=None,
        min_length=1,
        description="刷新令牌，应急账户不签发",
    )

    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="令牌类型",
    )

    expires_in: int = Field(
        ...,
        gt=0,
        description="访问令牌有效时间，单位为秒",
    )


class AccessTokenClaims(
    AuthSchema
):
    """访问令牌声明"""

    sub: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="用户 ID",
    )

    type: Literal["access"] = Field(
        ...,
        description="令牌类型",
    )

    iat: int = Field(
        ...,
        ge=0,
        description="令牌签发时间，Unix 时间戳",
    )

    exp: int = Field(
        ...,
        ge=0,
        description="令牌过期时间，Unix 时间戳",
    )

    username: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="登录用户名",
    )

    roles: list[str] = Field(
        default_factory=list,
        description="角色名称列表",
    )

    permissions: list[str] = Field(
        default_factory=list,
        description="权限标识列表",
    )


class AuthenticatedUser(
    AuthSchema
):
    """已认证用户信息"""

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="用户 ID",
    )

    username: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="登录用户名",
    )

    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="用户显示名称",
    )

    email: str | None = Field(
        default=None,
        min_length=1,
        max_length=254,
        description="用户邮箱",
    )

    status: UserStatus = Field(
        ...,
        description="用户状态",
    )

    roles: list[str] = Field(
        default_factory=list,
        description="角色名称列表",
    )

    permissions: list[str] = Field(
        default_factory=list,
        description="权限标识列表",
    )


__all__ = [
    "AuthSchema",
    "LoginRequest",
    "RefreshTokenRequest",
    "LogoutRequest",
    "LogoutResult",
    "TokenResponse",
    "AccessTokenClaims",
    "AuthenticatedUser",
]
