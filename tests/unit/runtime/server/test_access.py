"""运行时访问日志测试.

验证响应结果、异常和流式响应的日志记录及请求上下文恢复。

核心功能：
  - test_access_log_records_response: 验证状态码和请求标识
  - test_access_log_records_unhandled_exception: 验证异常日志
  - test_streaming_response_logged_once_after_body: 验证流式响应只记录一次
  - test_non_http_scope_passes_through: 验证非 HTTP 调用透传
"""

import logging
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse, StreamingResponse
from starlette.types import Receive, Scope, Send

from datamind.context import get_context
from datamind.runtime.server import access


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 401, 404, 422, 500])
@pytest.mark.parametrize("client_address", [("127.0.0.1", 123), None])
async def test_access_log_records_response(
        monkeypatch: pytest.MonkeyPatch,
        status_code: int,
        client_address: tuple[str, int] | None,
) -> None:
    """测试各类响应记录状态和处理请求所用的标识."""
    logger = MagicMock()
    monkeypatch.setattr(access, "logger", logger)
    before = get_context().copy()
    trace_id = "1" * 32

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        assert get_context()["request_id"] == "req_test"
        assert get_context()["trace_id"] == trace_id
        assert get_context()["ip"] == (
            client_address[0] if client_address is not None else None
        )
        # 受保护的接口会生成自己的预测请求 ID。
        scope[access.REQUEST_ID_SCOPE_KEY] = "req_prediction"
        scope[access.USER_SCOPE_KEY] = "admin"
        await JSONResponse({}, status_code=status_code)(scope, receive, send)

    middleware = access.AccessLogMiddleware(app)

    async def request_app(scope: Scope, receive: Receive, send: Send) -> None:
        scope["client"] = client_address
        await middleware(scope, receive, send)

    async with AsyncClient(
        transport=ASGITransport(app=request_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/predict?token=secret",
            headers={"x-request-id": "req_test", "x-trace-id": trace_id},
        )

    assert response.status_code == status_code
    logger.log.assert_called_once()
    assert logger.log.call_args.args == (logging.INFO, "HTTP 请求完成")
    fields = logger.log.call_args.kwargs
    assert fields["method"] == "POST"
    assert fields["path"] == "/predict"
    assert fields["status_code"] == status_code
    assert fields["trace_id"] == trace_id
    assert fields["request_id"] == "req_prediction"
    assert fields["user"] == "admin"
    assert fields["response_completed"] is True
    assert fields["duration_ms"] >= 0
    assert "secret" not in str(logger.log.call_args)
    assert get_context() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/ready"])
@pytest.mark.parametrize("status_code", [200, 204, 400, 503])
async def test_health_check_log_level(
        monkeypatch: pytest.MonkeyPatch,
        path: str,
        status_code: int,
) -> None:
    """仅将成功完成的健康检查访问日志降为 DEBUG."""
    logger = MagicMock()
    monkeypatch.setattr(access, "logger", logger)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({}, status_code=status_code)(scope, receive, send)

    async with AsyncClient(
        transport=ASGITransport(app=access.AccessLogMiddleware(app)),
        base_url="http://test",
    ) as client:
        await client.post(path)

    level = logging.DEBUG if status_code < 300 else logging.INFO
    logger.log.assert_called_once()
    assert logger.log.call_args.args == (level, "HTTP 请求完成")
    assert logger.log.call_args.kwargs["status_code"] == status_code


@pytest.mark.asyncio
async def test_access_log_records_unhandled_exception(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试异常记录为中断且不吞掉原始异常."""
    logger = MagicMock()
    monkeypatch.setattr(access, "logger", logger)
    before = get_context().copy()

    async def app(
            _scope: Scope,
            _receive: Receive,
            _send: Send,
    ) -> None:
        raise RuntimeError("failed")

    async with AsyncClient(
        transport=ASGITransport(app=access.AccessLogMiddleware(app)),
        base_url="http://test",
    ) as client:
        with pytest.raises(RuntimeError, match="failed"):
            await client.get("/predict")

    assert logger.log.call_args.kwargs["status_code"] == 500
    assert logger.log.call_args.kwargs["response_completed"] is False
    assert get_context() == before


@pytest.mark.asyncio
async def test_streaming_response_logged_once_after_body(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试流式响应在正文传送完成后只记录一次."""
    logger = MagicMock()
    monkeypatch.setattr(access, "logger", logger)

    async def chunks() -> AsyncIterator[bytes]:
        yield b"first"
        logger.log.assert_not_called()
        yield b"second"

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await StreamingResponse(chunks())(scope, receive, send)

    async with AsyncClient(
        transport=ASGITransport(app=access.AccessLogMiddleware(app)),
        base_url="http://test",
    ) as client:
        response = await client.get("/stream")

    assert response.content == b"firstsecond"
    logger.log.assert_called_once()
    assert logger.log.call_args.kwargs["response_completed"] is True


@pytest.mark.asyncio
async def test_non_http_scope_passes_through(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非 HTTP 调用透传且不产生访问日志."""
    logger = MagicMock()
    monkeypatch.setattr(access, "logger", logger)

    async def app(
            scope: Scope,
            _receive: Receive,
            _send: Send,
    ) -> None:
        assert scope["type"] == "lifespan"

    await access.AccessLogMiddleware(app)(
        {"type": "lifespan"},
        AsyncMock(),
        AsyncMock(),
    )
    logger.log.assert_not_called()
