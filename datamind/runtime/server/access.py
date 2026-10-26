"""运行时 HTTP 访问日志.

绑定请求日志上下文，并记录响应状态和请求耗时。

核心功能：
  - AccessLogMiddleware: 记录 HTTP 请求结果

使用示例：
  from datamind.runtime.server.access import AccessLogMiddleware

  # 为 BentoML 服务注册 HTTP 访问日志中间件
  service.add_asgi_middleware(
      AccessLogMiddleware
  )
"""

from time import perf_counter
from typing import Final

import structlog
from starlette.requests import Request
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from datamind.context import generate_trace_id, is_valid_trace_id
from datamind.context.scope import context_scope
from datamind.utils import generate_random_id


logger = structlog.get_logger(__name__)
REQUEST_ID_SCOPE_KEY: Final[str] = "datamind.request_id"
USER_SCOPE_KEY: Final[str] = "datamind.user"


class AccessLogMiddleware:
    """记录 HTTP 请求结果并绑定请求上下文."""

    def __init__(
            self,
            app: ASGIApp,
    ) -> None:
        """初始化访问日志中间件.

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
        """执行请求并记录响应结果."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = request.headers.get(
            "x-request-id",
            "",
        ).strip()
        if not request_id or len(request_id) > 64:
            request_id = generate_random_id(prefix="req")
        scope[REQUEST_ID_SCOPE_KEY] = request_id
        trace_id = scope.get("trace_id")
        if not isinstance(trace_id, str) or not is_valid_trace_id(trace_id):
            parts = request.headers.get(
                "traceparent",
                "",
            ).strip().lower().split("-")
            trace_id = (
                parts[1]
                if len(parts) == 4 and is_valid_trace_id(parts[1])
                else request.headers.get(
                    "x-trace-id",
                    "",
                ).strip().lower()
            )
            if not is_valid_trace_id(trace_id):
                trace_id = generate_trace_id()
            scope["trace_id"] = trace_id

        started = perf_counter()
        status_code = 500
        completed = False

        async def send_response(
                message: Message,
        ) -> None:
            """传递响应并记录状态和正文完成情况."""
            nonlocal status_code, completed
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
            if (
                    message["type"] == "http.response.body"
                    and not message.get("more_body", False)
            ):
                completed = True

        client = request.client

        with context_scope(
                request_id=request_id,
                trace_id=trace_id,
                source="http",
                ip=client.host if client is not None else None,
        ):
            try:
                await self.app(scope, receive, send_response)
            finally:
                logger.info(
                    "HTTP 请求完成" if completed else "HTTP 请求中断",
                    method=request.method,
                    path=scope["path"],
                    status_code=status_code,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    request_id=scope[REQUEST_ID_SCOPE_KEY],
                    user=scope.get(USER_SCOPE_KEY),
                    response_completed=completed,
                )
