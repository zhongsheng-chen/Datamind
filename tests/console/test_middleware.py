# tests/console/test_middleware.py

"""管理控制台安全响应头测试

验证控制台中间件为 HTTP 响应附加浏览器安全策略。

核心功能：
  - test_security_headers_adds_browser_protections: 验证通用安全响应头
  - test_security_headers_adds_hsts_only_for_https: 验证 HSTS 使用条件
"""

from httpx import (
    ASGITransport,
    AsyncClient,
)
import pytest
from starlette.responses import PlainTextResponse

from datamind.console.middleware import security_headers


async def app(scope, receive, send) -> None:
    """返回安全响应头测试页面"""
    response = PlainTextResponse("ok")
    await response(scope, receive, send)


@pytest.mark.asyncio
async def test_security_headers_adds_browser_protections() -> None:
    """测试 HTTP 响应包含通用浏览器安全头"""
    async with AsyncClient(
            transport=ASGITransport(
                app=security_headers(app)
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.headers[
        "content-security-policy"
    ].startswith("default-src 'self'")
    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"
    assert response.headers[
        "referrer-policy"
    ] == "no-referrer"
    assert response.headers[
        "permissions-policy"
    ] == "camera=(), microphone=(), geolocation=()"
    assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio
async def test_security_headers_adds_hsts_only_for_https() -> None:
    """测试 HTTPS 响应启用严格传输安全策略"""
    async with AsyncClient(
            transport=ASGITransport(
                app=security_headers(app)
            ),
            base_url="https://testserver",
    ) as client:
        response = await client.get("/")

    assert response.headers[
        "strict-transport-security"
    ] == "max-age=31536000"
