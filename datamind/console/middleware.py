"""管理控制台 HTTP 中间件.

负责绑定请求日志上下文，并为浏览器响应附加安全策略和防护响应头。

核心功能：
  - RequestContextMiddleware: 管理 HTTP 请求日志上下文
  - SecurityHeadersMiddleware: 为控制台响应增加浏览器安全头
  - security_headers: 创建安全响应头中间件
"""

from collections.abc import Callable

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from datamind.context.scope import context_scope


class RequestContextMiddleware:
    """在 HTTP 请求生命周期内绑定日志上下文."""

    def __init__(
            self,
            app: ASGIApp,
            context_factory: Callable[[Request], dict[str, object]],
    ) -> None:
        """初始化请求上下文中间件.

        参数：
            app: 下游 ASGI 应用
            context_factory: 根据请求创建日志上下文的函数
        """
        self.app = app
        self.context_factory = context_factory

    async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        context = self.context_factory(request)

        with context_scope(**context):
            await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """为控制台响应增加浏览器安全头."""

    def __init__(
            self,
            app: ASGIApp,
    ) -> None:
        """初始化安全响应头中间件.

        参数：
            app: 下游 ASGI 应用
        """
        self.app = app

    async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send,
    ) -> None:
        async def send_with_headers(
                message: Message,
        ) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(
                    scope=message
                )
                headers["content-security-policy"] = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self'; "
                    "img-src 'self' data:; "
                    "connect-src 'self'; "
                    "object-src 'none'; "
                    "base-uri 'self'; "
                    "frame-ancestors 'none'; "
                    "form-action 'self'"
                )
                headers["x-content-type-options"] = "nosniff"
                headers["referrer-policy"] = "no-referrer"
                headers["permissions-policy"] = (
                    "camera=(), microphone=(), geolocation=()"
                )

                if scope.get("scheme") == "https":
                    headers["strict-transport-security"] = (
                        "max-age=31536000"
                    )

            await send(
                message
            )

        await self.app(
            scope,
            receive,
            send_with_headers,
        )


def security_headers(
        app: ASGIApp,
        /,
) -> ASGIApp:
    """创建安全响应头中间件."""
    return SecurityHeadersMiddleware(
        app
    )
