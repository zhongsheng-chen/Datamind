"""管理控制台 HTTP 响应.

负责构造通用错误响应并读取请求端信息。

核心功能：
  - error_response: 创建统一错误响应
  - client_ip: 读取客户端 IP
"""

from starlette.requests import Request
from starlette.responses import JSONResponse


def client_ip(
        request: Request,
) -> str | None:
    """读取客户端 IP."""
    client = request.client

    if client is None:
        return None

    return client.host


def error_response(
        message: str,
        *,
        status_code: int,
) -> JSONResponse:
    """创建统一错误响应."""
    return JSONResponse(
        {
            "error": message
        },
        status_code=status_code,
    )
