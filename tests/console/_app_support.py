"""Console HTTP 契约测试公共支持.

集中提供拆分后的 Console 测试共用替身对象和请求构造器，避免各测试模块重复维护
同一套测试基础设施。

核心功能：
  - FakeUnitOfWork: 提供最小异步工作单元替身
  - create_user: 创建标准已认证测试用户
  - FakeEventBroker: 提供 SSE 订阅替身
  - create_event_request: 构造 SSE 请求对象
  - timeout_wait_for: 模拟 SSE 心跳超时
"""

import asyncio
import importlib
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from starlette.requests import Request

from datamind.auth.enums import UserStatus
from datamind.auth.schemas import AuthenticatedUser


app_module = importlib.import_module("datamind.console.app")


class FakeUnitOfWork:
    """提供 Console 应用测试使用的最小工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_user() -> AuthenticatedUser:
    """创建标准的 Console 已认证测试用户."""
    return AuthenticatedUser(
        user_id="usr_alice",
        username="alice",
        display_name="Alice",
        email="alice@example.com",
        status=UserStatus.ACTIVE,
        roles=["developer"],
        permissions=["model.read"],
    )


class FakeEventBroker:
    """提供 Console SSE 契约测试使用的最小事件代理."""

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[int]]:
        yield asyncio.Queue()


def create_event_request(last_event_id: str | None = None) -> Request:
    """创建用于执行 SSE 生成器的请求对象."""
    headers: list[tuple[bytes, bytes]] = []
    if last_event_id is not None:
        headers.append((b"last-event-id", last_event_id.encode("ascii")))

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/events",
            "headers": headers,
        },
        receive,
    )


async def timeout_wait_for(
    awaitable: Coroutine[object, object, object],
    *,
    timeout: float,
) -> None:
    """关闭待处理协程并模拟 SSE 心跳超时."""
    assert timeout > 0
    awaitable.close()
    raise TimeoutError
