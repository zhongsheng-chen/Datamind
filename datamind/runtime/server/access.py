"""运行时 HTTP 访问日志.

绑定请求日志上下文，并记录响应状态和请求耗时。

核心功能：
  - AccessLogMiddleware: 记录 HTTP 请求结果
  - get_trace_id: 获取当前请求的链路追踪 ID

使用示例：
  from datamind.runtime.server.access import AccessLogMiddleware

  # 为 BentoML 服务注册 HTTP 访问日志中间件
  service.add_asgi_middleware(
      AccessLogMiddleware
  )
"""

import logging
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
TRACE_ID_SCOPE_KEY: Final[str] = "datamind.trace_id"
USER_SCOPE_KEY: Final[str] = "datamind.user"
RESULT_SCOPE_KEY: Final[str] = "datamind.result"


def get_trace_id(
        request: Request,
) -> str:
    """获取当前请求的链路追踪 ID.

    优先使用请求作用域中已有的有效 ID，其次读取
    traceparent 或 x-trace-id 请求头，均无有效值时生成新 ID。
    结果保存在请求作用域中，供同一请求的日志和审计复用。

    参数：
        request: 当前 HTTP 请求

    返回：
        32 位小写十六进制格式且不全为零的链路追踪 ID
    """
    trace_id = request.scope.get(
        TRACE_ID_SCOPE_KEY
    )

    if (
            isinstance(trace_id, str)
            and is_valid_trace_id(trace_id)
    ):
        return trace_id

    trace_id = request.scope.get(
        "trace_id"
    )

    if (
            not isinstance(trace_id, str)
            or not is_valid_trace_id(trace_id)
    ):
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

    request.scope[TRACE_ID_SCOPE_KEY] = trace_id

    return trace_id


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
        trace_id = get_trace_id(request)

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
                is_successful_probe = (
                    completed
                    and 200 <= status_code < 300
                    and scope["path"] in {"/health", "/ready"}
                )
                level = logging.DEBUG if is_successful_probe else logging.INFO
                logger.log(
                    level,
                    "HTTP 请求完成" if completed else "HTTP 请求中断",
                    method=request.method,
                    path=scope["path"],
                    status_code=status_code,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    trace_id=trace_id,
                    request_id=scope[REQUEST_ID_SCOPE_KEY],
                    user=scope.get(USER_SCOPE_KEY),
                    response_completed=completed,
                    **scope.get(RESULT_SCOPE_KEY, {}),
                )
