"""运行时认证接口

提供登录、令牌续期和退出接口，并统一构造认证响应。

核心功能：
  - AuthenticationMixin: 提供运行时认证相关的 BentoML 接口

使用示例：
  from datamind.runtime.server.authentication import AuthenticationMixin

  class RuntimeService(AuthenticationMixin):
      pass
"""

from typing import Any

import bentoml
from pydantic import SecretStr
from sqlalchemy.exc import SQLAlchemyError

from datamind.auth.errors import (
    AuthError,
    InvalidCredentialsError,
    TokenError,
    UserDisabledError,
    UserLockedError,
)
from datamind.auth.factory import create_auth_service
from datamind.auth.schemas import LoginRequest, LogoutRequest, RefreshTokenRequest
from datamind.db.core import UnitOfWork


class AuthenticationMixin:
    """运行时认证接口能力"""

    @bentoml.api(
        route="/auth/login",
    )
    async def login(
            self,
            username: str,
            password: SecretStr,
        ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """使用本地用户名和密码登录"""
        self._set_auth_response_headers(
            ctx
        )

        try:
            async with UnitOfWork() as uow:
                service = create_auth_service(
                    session=uow.session
                )

                try:
                    tokens = await service.login(
                        LoginRequest(
                            username=username,
                            password=password,
                        ),
                        ip=self._request_ip(
                            ctx
                        ),
                        user_agent=ctx.request.headers.get(
                            "user-agent"
                        ),
                    )
                except (
                        InvalidCredentialsError,
                        UserDisabledError,
                        UserLockedError,
                ):
                    return self._auth_error_response(
                        ctx=ctx,
                        message="用户名或密码错误",
                        status_code=401,
                    )
        except (
                AuthError,
                SQLAlchemyError,
                ValueError,
        ):
            return self._auth_error_response(
                ctx=ctx,
                message="认证服务暂不可用",
                status_code=503,
            )

        return tokens.model_dump(
            mode="json"
        )

    @bentoml.api(
        route="/auth/refresh",
    )
    async def refresh(
            self,
            refresh_token: SecretStr,
        ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """续期并轮换刷新令牌"""
        self._set_auth_response_headers(
            ctx
        )

        try:
            async with UnitOfWork() as uow:
                service = create_auth_service(
                    session=uow.session
                )

                try:
                    tokens = await service.refresh(
                        RefreshTokenRequest(
                            refresh_token=refresh_token
                        ),
                        ip=self._request_ip(
                            ctx
                        ),
                        user_agent=ctx.request.headers.get(
                            "user-agent"
                        ),
                    )
                except (
                        TokenError,
                        UserDisabledError,
                        UserLockedError,
                ):
                    return self._auth_error_response(
                        ctx=ctx,
                        message="刷新令牌无效或已失效",
                        status_code=401,
                    )
        except (
                AuthError,
                SQLAlchemyError,
                ValueError,
        ):
            return self._auth_error_response(
                ctx=ctx,
                message="认证服务暂不可用",
                status_code=503,
            )

        return tokens.model_dump(
            mode="json"
        )

    @bentoml.api(
        route="/auth/logout",
    )
    async def logout(
            self,
            refresh_token: SecretStr,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """撤销刷新令牌"""
        self._set_auth_response_headers(
            ctx
        )

        try:
            async with UnitOfWork() as uow:
                service = create_auth_service(
                    session=uow.session
                )
                await service.logout(
                    LogoutRequest(
                        refresh_token=refresh_token
                    )
                )
        except (
                AuthError,
                SQLAlchemyError,
                ValueError,
        ):
            return self._auth_error_response(
                ctx=ctx,
                message="认证服务暂不可用",
                status_code=503,
            )

        ctx.response.status_code = 204

        return {}

    @staticmethod
    def _set_auth_response_headers(
        ctx: bentoml.Context,
    ) -> None:
        """禁止缓存认证响应"""
        ctx.response.headers[
            "Cache-Control"
        ] = "no-store"
        ctx.response.headers[
            "Pragma"
        ] = "no-cache"

    @staticmethod
    def _auth_error_response(
            *,
            ctx: bentoml.Context,
            message: str,
            status_code: int,
    ) -> dict[str, Any]:
        """构造认证错误响应"""
        ctx.response.status_code = status_code

        return {
            "error": message,
        }

    @staticmethod
    def _request_ip(
            ctx: bentoml.Context,
    ) -> str | None:
        """读取客户端 IP"""
        client = ctx.request.client

        return (
            client.host
            if client is not None
            else None
        )
