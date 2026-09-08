"""管理控制台 HTTP 响应测试

验证通用错误响应结构与客户端地址读取行为。

核心功能：
  - test_error_response_uses_consistent_payload: 验证错误响应结构
  - test_client_ip_reads_request_client: 验证客户端地址读取
  - test_client_ip_returns_none_without_client: 验证缺失客户端地址
"""

import json

from starlette.requests import Request

from datamind.console.responses import (
    client_ip,
    error_response,
)


def test_error_response_uses_consistent_payload() -> None:
    """测试错误响应包含统一字段和状态码"""
    response = error_response(
        "请求无效",
        status_code=422,
    )

    assert response.status_code == 422
    assert json.loads(response.body) == {
        "error": "请求无效"
    }


def test_client_ip_reads_request_client() -> None:
    """测试从请求连接信息读取客户端 IP"""
    request = Request(
        {
            "type": "http",
            "client": ("192.0.2.10", 50123),
            "headers": [],
        }
    )

    assert client_ip(request) == "192.0.2.10"


def test_client_ip_returns_none_without_client() -> None:
    """测试请求没有连接信息时返回空值"""
    request = Request(
        {
            "type": "http",
            "client": None,
            "headers": [],
        }
    )

    assert client_ip(request) is None
