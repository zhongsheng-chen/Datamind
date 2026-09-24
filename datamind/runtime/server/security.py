"""运行时服务安全边界.

负责解析 Bearer 访问令牌、认证用户、校验接口权限，
并为日志和审计建立可信请求上下文。

核心功能：
  - RuntimeIdentity: 保存已认证的运行时请求身份
  - RuntimeRequestContext: 定义运行时请求上下文协议
  - RuntimeSecurity: 提供运行时认证与授权边界
  - request_scope: 建立已认证请求作用域
  - authenticate: 认证访问令牌并校验接口权限

使用示例：
  from datamind.runtime.server.security import RuntimeSecurity

  security = RuntimeSecurity()

  async with security.request_scope(
      context=ctx,
      permission="prediction.invoke",
      request_id="req_0123456789abcdef",
  ) as identity:
      print(identity.username)
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from starlette.requests import Request

from datamind.auth.errors import AuthError, PermissionDeniedError
from datamind.auth.factory import create_auth_service
from datamind.auth.permissions import require_permission
from datamind.config.providers import (
    get_auth_config,
    get_service_config,
)
from datamind.constants import Environment
from datamind.context.scope import context_scope
from datamind.db.core import UnitOfWork
from datamind.runtime.server.errors import (
    ServiceAuthenticationError,
    ServiceAuthenticationUnavailableError,
    ServiceAuthorizationError,
)


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """运行时请求身份."""

    user_id: str
    username: str
    permissions: tuple[str, ...]
    authenticated: bool


class RuntimeRequestContext(Protocol):
    """运行时请求上下文协议."""

    @property
    def request(self) -> Request:
        """返回当前 HTTP 请求."""
        ...


class RuntimeSecurity:
    """运行时服务安全边界."""

    @asynccontextmanager
    async def request_scope(
            self,
            *,
            context: RuntimeRequestContext,
            permission: str,
            request_id: str,
    ) -> AsyncIterator[RuntimeIdentity]:
        """认证请求并建立可信上下文."""
        identity = await self.authenticate(
            context=context,
            permission=permission,
        )
        request = context.request
        client = request.client
        ip = (
            client.host
            if client is not None
            else None
        )

        with context_scope(
                user=identity.username,
                ip=ip,
                hostname=None,
                trace_id=self._scope_value(
                    request.scope,
                    "trace_id",
                ),
                request_id=request_id,
                source="http",
        ):
            yield identity

    async def authenticate(
            self,
            *,
            context: RuntimeRequestContext,
            permission: str,
    ) -> RuntimeIdentity:
        """认证请求并校验权限."""
        auth_config = get_auth_config()
        service_config = get_service_config()

        if not auth_config.enabled:
            if service_config.environment in (
                    Environment.STAGING,
                    Environment.PRODUCTION,
            ):
                raise ServiceAuthenticationUnavailableError(
                    "预发布和生产环境必须启用认证"
                )

            return RuntimeIdentity(
                user_id="system",
                username="system",
                permissions=("*",),
                authenticated=False,
            )

        access_token = self._extract_bearer_token(
            context.request.headers.get(
                "authorization"
            )
        )

        try:
            async with UnitOfWork() as uow:
                service = create_auth_service(
                    session=uow.session
                )
                user = await service.authenticate_access_token(
                    access_token
                )

        except AuthError as exc:
            raise ServiceAuthenticationError(
                "访问令牌无效或已失效"
            ) from exc

        try:
            require_permission(
                granted_permissions=user.permissions,
                required_permission=permission,
            )

        except PermissionDeniedError as exc:
            raise ServiceAuthorizationError(
                f"缺少接口权限: {permission}"
            ) from exc

        return RuntimeIdentity(
            user_id=user.user_id,
            username=user.username,
            permissions=tuple(
                user.permissions
            ),
            authenticated=True,
        )

    @staticmethod
    def _extract_bearer_token(
            authorization: str | None,
    ) -> str:
        """解析 Authorization Bearer 令牌."""
        if authorization is None:
            raise ServiceAuthenticationError(
                "缺少 Authorization Bearer 访问令牌"
            )

        scheme, separator, token = authorization.partition(
            " "
        )

        if (
                separator == ""
                or scheme.lower() != "bearer"
                or token.strip() == ""
        ):
            raise ServiceAuthenticationError(
                "Authorization 必须使用 Bearer 访问令牌"
            )

        return token.strip()

    @staticmethod
    def _scope_value(
            scope: Mapping[str, Any],
            key: str,
    ) -> str | None:
        """读取字符串请求作用域字段."""
        value = scope.get(
            key
        )

        return (
            value
            if isinstance(value, str)
            else None
        )
