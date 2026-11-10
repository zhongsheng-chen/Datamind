"""管理控制台中间件测试.

验证控制台请求日志上下文隔离、浏览器安全响应头及依赖连接异常处理。

核心功能：
  - test_dependency_outage_returns_retryable_503:
    验证连接异常返回可重试的 503 响应且不泄露底层错误信息
  - test_dependency_middleware_does_not_hide_programming_errors:
    验证依赖异常处理中间件继续传播代码错误
  - test_request_context_matches_audit:
    验证日志和审计上下文一致及退出恢复
  - test_request_context_isolates_concurrent_requests:
    验证并发请求上下文隔离
  - test_security_headers_adds_browser_protections:
    验证通用安全响应头
  - test_security_headers_adds_hsts_only_for_https:
    验证 HSTS 使用条件
  - test_http_audit_context_generates_missing_identifiers:
    验证控制台为缺失标识的 HTTP 审计补全上下文
  - test_dependency_middleware_preserves_started_response:
    验证事件流断连后不重复发送 HTTP 响应头
  - test_windows_network_timeout_is_503_but_file_error_propagates:
    验证Windows 网络超时返回 503 且本地文件错误继续传播
"""

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

from httpx import (
    ASGITransport,
    AsyncClient,
)
import pytest
from starlette.responses import PlainTextResponse
from starlette.requests import Request

from datamind.audit.enums import AuditSource
from datamind.console.middleware import (
    DependencyUnavailableMiddleware,
    RequestContextMiddleware,
    security_headers,
)
from datamind.context.core import get_context
from datamind.context.scope import context_scope
from datamind.logging.processors import add_context
from tests.console._app_support import app_module, create_user


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [ConnectionRefusedError('offline'), TimeoutError('timeout')])
async def test_dependency_outage_returns_retryable_503(error):
    """测试连接异常返回可重试的 503 响应且不泄露底层错误信息."""
    async def unavailable(_scope, _receive, _send):
        raise error

    async with AsyncClient(
        transport=ASGITransport(app=security_headers(DependencyUnavailableMiddleware(unavailable))),
        base_url='http://testserver',
    ) as client:
        response = await client.get('/events')
    assert response.status_code == 503
    assert response.headers['retry-after'] == '5'
    assert 'content-security-policy' in response.headers
    assert response.json() == {'error': '数据库连接暂不可用，请稍后重试'}


@pytest.mark.asyncio
async def test_dependency_middleware_does_not_hide_programming_errors():
    """测试依赖异常处理中间件继续传播代码错误."""
    async def broken(_scope, _receive, _send):
        raise ValueError('bug')

    async with AsyncClient(
        transport=ASGITransport(app=DependencyUnavailableMiddleware(broken)),
        base_url='http://testserver',
    ) as client:
        with pytest.raises(ValueError, match='bug'):
            await client.get('/')


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_request_context_matches_audit(
    monkeypatch: pytest.MonkeyPatch,
    fail: bool,
) -> None:
    """测试日志与审计使用相同上下文且异常后恢复外层上下文."""
    console = importlib.import_module("datamind.console.app")
    user = SimpleNamespace(
        username="admin",
        actor={},
    )
    monkeypatch.setitem(
        vars(console.browser_auth),
        "authenticate",
        AsyncMock(return_value=user),
    )
    observed = {}

    async def handler(scope, receive, send) -> None:
        request = Request(scope)
        authenticated = await console._authenticate(request)
        observed["audit"] = console._http_audit_context(
            request,
            user=authenticated,
        )
        observed["log"] = add_context()(None, "info", {})
        if fail:
            raise RuntimeError("request failed")
        await app(scope, receive, send)

    middleware = RequestContextMiddleware(
        handler,
        context_factory=console._http_actor_context,
    )
    with context_scope(request_id="outer", user="outer"):
        previous = get_context().copy()
        async with AsyncClient(
            transport=ASGITransport(app=middleware),
            base_url="http://testserver",
        ) as client:
            if fail:
                with pytest.raises(RuntimeError, match="request failed"):
                    await client.get("/")
            else:
                response = await client.get("/")
                assert response.status_code == 200

        assert get_context() == previous

    assert observed["audit"]["request_id"].startswith("req_")
    assert len(observed["audit"]["trace_id"]) == 32
    for key, value in observed["audit"].items():
        assert observed["log"][key] == value


@pytest.mark.asyncio
async def test_request_context_isolates_concurrent_requests() -> None:
    """测试并发请求在等待后仍保留各自的请求标识."""
    console = importlib.import_module("datamind.console.app")
    entered = 0
    ready = asyncio.Event()
    observed = {}

    async def handler(scope, receive, send) -> None:
        nonlocal entered
        request = Request(scope)
        entered += 1
        if entered == 2:
            ready.set()
        await asyncio.wait_for(ready.wait(), timeout=5)
        observed[request.url.path] = get_context().copy()
        await app(scope, receive, send)

    middleware = RequestContextMiddleware(
        handler,
        context_factory=console._http_actor_context,
    )
    previous = get_context().copy()
    async with AsyncClient(
        transport=ASGITransport(app=middleware),
        base_url="http://testserver",
    ) as client:
        await asyncio.gather(
            client.get("/first", headers={"X-Request-ID": "req_first"}),
            client.get("/second", headers={"X-Request-ID": "req_second"}),
        )

    assert observed["/first"]["request_id"] == "req_first"
    assert observed["/second"]["request_id"] == "req_second"
    assert observed["/first"]["trace_id"] != observed["/second"]["trace_id"]
    assert get_context() == previous


async def app(scope, receive, send) -> None:
    """返回安全响应头测试页面."""
    response = PlainTextResponse("ok")
    await response(scope, receive, send)


@pytest.mark.asyncio
async def test_security_headers_adds_browser_protections() -> None:
    """测试 HTTP 响应包含通用浏览器安全头."""
    async with AsyncClient(
        transport=ASGITransport(app=security_headers(app)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert (
        response.headers["permissions-policy"]
        == "camera=(), microphone=(), geolocation=()"
    )
    assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio
async def test_security_headers_adds_hsts_only_for_https() -> None:
    """测试 HTTPS 响应启用严格传输安全策略."""
    async with AsyncClient(
        transport=ASGITransport(app=security_headers(app)),
        base_url="https://testserver",
    ) as client:
        response = await client.get("/")

    assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_http_audit_context_generates_missing_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台为缺失标识的 HTTP 审计补全上下文."""
    monkeypatch.setitem(
        vars(app_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_generated",
    )
    monkeypatch.setitem(
        vars(app_module),
        "generate_trace_id",
        lambda: "fedcba9876543210fedcba9876543210",
    )
    monkeypatch.setitem(
        vars(app_module),
        "get_hostname",
        lambda: "console-host",
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/api/deployments",
            "raw_path": b"/api/deployments",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("localhost", 80),
        }
    )

    context = app_module._http_audit_context(
        request,
        user=create_user(),
    )

    assert context == {
        "user": "alice",
        "source": AuditSource.HTTP,
        "ip": "127.0.0.1",
        "request_id": "req_generated",
        "trace_id": "fedcba9876543210fedcba9876543210",
        "hostname": "console-host",
    }


@pytest.mark.asyncio
async def test_dependency_middleware_preserves_started_response():
    """测试事件流断连后不重复发送 HTTP 响应头."""
    messages = []

    async def stream(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise ConnectionRefusedError("stream disconnected")

    async def capture_send(message):
        messages.append(message)

    with pytest.raises(ConnectionRefusedError):
        await DependencyUnavailableMiddleware(stream)({"type": "http"}, AsyncMock(), capture_send)
    assert len(messages) == 1
    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_windows_network_timeout_is_503_but_file_error_propagates():
    """测试 Windows 网络超时返回 503 且本地文件错误继续传播."""
    error = OSError("network timeout")
    error.winerror = 121

    async def unavailable(_scope, _receive, _send):
        raise error

    async with AsyncClient(
        transport=ASGITransport(app=DependencyUnavailableMiddleware(unavailable)),
        base_url="http://testserver",
    ) as client:
        assert (await client.get("/")).status_code == 503
        error = FileNotFoundError("missing local file")
        with pytest.raises(FileNotFoundError):
            await client.get("/")
