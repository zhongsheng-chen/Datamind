"""Console 应用入口测试

验证控制台首页、健康检查、安全响应头和应用生命周期。

核心功能：
  - test_console_page_is_available: 验证首页和健康检查可访问
  - test_console_is_ready_when_database_is_available:
    验证数据库可用时控制台进入就绪状态
  - test_console_is_not_ready_when_database_is_unavailable:
    验证数据库不可用时控制台返回未就绪状态
  - test_lifespan_starts_and_stops_event_broker: 验证事件代理生命周期
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from tests.console._app_support import app_module


@pytest.mark.asyncio
async def test_console_page_is_available() -> None:
    """测试控制台页面、健康检查和安全响应头"""
    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/")
        health = await client.get("/health")

    assert response.status_code == 200
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert "Datamind 管理控制台" in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def replace_unit_of_work(
        monkeypatch: pytest.MonkeyPatch,
        *,
        execute_error: Exception | None = None,
) -> None:
    """替换控制台工作单元并配置数据库探测结果"""
    unit_of_work = MagicMock()
    unit_of_work.__aenter__ = AsyncMock(return_value=unit_of_work)
    unit_of_work.__aexit__ = AsyncMock(return_value=False)
    unit_of_work.session.execute = AsyncMock(
        side_effect=execute_error,
    )
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        MagicMock(return_value=unit_of_work),
    )


@pytest.mark.asyncio
async def test_console_is_ready_when_database_is_available(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库可用时控制台进入就绪状态"""
    replace_unit_of_work(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database_ready": True,
    }


@pytest.mark.asyncio
async def test_console_is_not_ready_when_database_is_unavailable(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库不可用时控制台返回未就绪状态"""
    replace_unit_of_work(
        monkeypatch,
        execute_error=SQLAlchemyError("database unavailable"),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database_ready": False,
    }


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_event_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试应用生命周期管理事件代理"""
    broker = MagicMock()
    broker.start = AsyncMock()
    broker.stop = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        broker,
    )

    async with app_module._lifespan(app_module.console_app):
        broker.start.assert_awaited_once_with()
        broker.stop.assert_not_awaited()

    broker.stop.assert_awaited_once_with()
