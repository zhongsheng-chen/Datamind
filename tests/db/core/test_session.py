"""数据库会话工厂测试

验证异步会话工厂的创建参数、单例缓存和重置行为。

核心功能：
  - test_get_session_factory_creates_factory:
    验证首次调用创建会话工厂
  - test_get_session_factory_returns_cached_factory:
    验证后续调用返回同一会话工厂
  - test_get_session_factory_uses_existing_factory:
    验证已有会话工厂时不再获取数据库引擎
  - test_reset_session_factory:
    验证重置会话工厂
  - test_reset_session_factory_is_idempotent:
    验证重复重置保持幂等
  - test_get_session_factory_recreates_after_reset:
    验证重置后重新创建会话工厂
"""

from collections.abc import Iterator
from typing import cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

import datamind.db.core.session as session_module


@pytest.fixture(
    autouse=True
)
def reset_session_state() -> Iterator[None]:
    """隔离数据库会话工厂全局状态"""
    session_module._session_factory = None

    yield

    session_module._session_factory = None


def create_engine_mock() -> AsyncEngine:
    """创建异步数据库引擎测试替身"""
    return cast(
        AsyncEngine,
        MagicMock(
            spec=AsyncEngine
        ),
    )


def create_session_factory_mock(
) -> async_sessionmaker[AsyncSession]:
    """创建异步会话工厂测试替身"""
    return cast(
        async_sessionmaker[AsyncSession],
        MagicMock(
            spec=async_sessionmaker
        ),
    )


def test_get_session_factory_creates_factory(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证首次调用创建会话工厂"""
    engine = create_engine_mock()
    session_factory = (
        create_session_factory_mock()
    )
    get_engine = MagicMock(
        return_value=engine
    )
    async_sessionmaker_mock = MagicMock(
        return_value=session_factory
    )

    monkeypatch.setitem(
        vars(session_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setitem(
        vars(session_module),
        "async_sessionmaker",
        async_sessionmaker_mock,
    )

    result = session_module.get_session_factory()

    assert result is session_factory
    assert (
        session_module._session_factory
        is session_factory
    )
    get_engine.assert_called_once_with()
    async_sessionmaker_mock.assert_called_once_with(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


def test_get_session_factory_returns_cached_factory(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证后续调用返回同一会话工厂"""
    engine = create_engine_mock()
    session_factory = (
        create_session_factory_mock()
    )
    get_engine = MagicMock(
        return_value=engine
    )
    async_sessionmaker_mock = MagicMock(
        return_value=session_factory
    )

    monkeypatch.setitem(
        vars(session_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setitem(
        vars(session_module),
        "async_sessionmaker",
        async_sessionmaker_mock,
    )

    first = session_module.get_session_factory()
    second = session_module.get_session_factory()

    assert first is session_factory
    assert second is session_factory
    assert first is second
    get_engine.assert_called_once_with()
    async_sessionmaker_mock.assert_called_once()


def test_get_session_factory_uses_existing_factory(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证已有会话工厂时不再获取数据库引擎"""
    session_factory = (
        create_session_factory_mock()
    )
    get_engine = MagicMock()
    async_sessionmaker_mock = MagicMock()

    session_module._session_factory = (
        session_factory
    )

    monkeypatch.setitem(
        vars(session_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setitem(
        vars(session_module),
        "async_sessionmaker",
        async_sessionmaker_mock,
    )

    result = session_module.get_session_factory()

    assert result is session_factory
    get_engine.assert_not_called()
    async_sessionmaker_mock.assert_not_called()


def test_reset_session_factory() -> None:
    """验证重置会话工厂"""
    session_factory = (
        create_session_factory_mock()
    )
    session_module._session_factory = (
        session_factory
    )

    session_module.reset_session_factory()

    assert session_module._session_factory is None


def test_reset_session_factory_is_idempotent() -> None:
    """验证重复重置保持幂等"""
    session_module.reset_session_factory()
    session_module.reset_session_factory()

    assert session_module._session_factory is None


def test_get_session_factory_recreates_after_reset(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证重置后重新创建会话工厂"""
    engine = create_engine_mock()
    first_factory = (
        create_session_factory_mock()
    )
    second_factory = (
        create_session_factory_mock()
    )
    get_engine = MagicMock(
        return_value=engine
    )
    async_sessionmaker_mock = MagicMock(
        side_effect=[
            first_factory,
            second_factory,
        ]
    )

    monkeypatch.setitem(
        vars(session_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setitem(
        vars(session_module),
        "async_sessionmaker",
        async_sessionmaker_mock,
    )

    first = session_module.get_session_factory()

    session_module.reset_session_factory()

    second = session_module.get_session_factory()

    assert first is first_factory
    assert second is second_factory
    assert second is not first
    assert (
        session_module._session_factory
        is second_factory
    )
    assert get_engine.call_count == 2
    assert async_sessionmaker_mock.call_count == 2
