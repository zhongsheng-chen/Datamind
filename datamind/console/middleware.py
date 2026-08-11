# datamind/console/middleware.py

"""管理控制台 HTTP 中间件

负责为浏览器响应附加安全策略和防护响应头。

核心功能：
  - security_headers: 创建安全响应头中间件
"""

from starlette.datastructures import MutableHeaders
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)


class SecurityHeadersMiddleware:
    """为控制台响应增加浏览器安全头"""

    def __init__(
            self,
            app: ASGIApp,
    ) -> None:
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
    """创建安全响应头中间件"""
    return SecurityHeadersMiddleware(
        app
    )
