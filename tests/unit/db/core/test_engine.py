"""数据库引擎管理测试.

验证异步数据库引擎的创建参数、单例缓存和资源释放行为。

核心功能：
  - test_create_engine_uses_database_config:
    验证创建引擎时使用数据库配置
  - test_get_engine_creates_singleton:
    验证首次获取时创建引擎并缓存
  - test_get_engine_returns_existing_engine:
    验证已有引擎时直接返回
  - test_dispose_engine_disposes_existing_engine:
    验证关闭引擎并重置会话工厂
  - test_dispose_engine_without_existing_engine:
    验证无引擎时仍重置会话工厂
  - test_dispose_engine_clears_state_before_dispose:
    验证引擎释放失败时全局状态仍已清理
"""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

import datamind.db.core.engine as engine_module
import datamind.db.core.session as session_module


DATABASE_URL = (
    "postgresql+asyncpg://"
    "datamind:password@localhost:5432/datamind"
)


@pytest.fixture(
    autouse=True
)
def reset_engine_state() -> Iterator[None]:
    """隔离数据库引擎全局状态."""
    engine_module._engine = None

    yield

    engine_module._engine = None


def create_engine_mock() -> tuple[
    AsyncEngine,
    AsyncMock,
]:
    """创建异步引擎测试替身."""
    dispose = AsyncMock()
    engine = MagicMock(
        spec=AsyncEngine
    )
    engine.dispose = dispose

    return (
        cast(
            AsyncEngine,
            engine,
        ),
        dispose,
    )


def test_create_engine_uses_database_config(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建引擎时使用数据库配置."""
    engine, _ = create_engine_mock()
    database_config = SimpleNamespace(
        url=DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        echo=True,
    )
    get_database_config = MagicMock(
        return_value=database_config
    )
    create_async_engine = MagicMock(
        return_value=engine
    )

    monkeypatch.setitem(
        vars(engine_module),
        "get_database_config",
        get_database_config,
    )
    monkeypatch.setitem(
        vars(engine_module),
        "create_async_engine",
        create_async_engine,
    )

    result = engine_module.create_engine()

    assert result is engine
    get_database_config.assert_called_once_with()
    create_async_engine.assert_called_once_with(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        echo=True,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,
        },
    )


def test_get_engine_creates_singleton(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次获取时创建引擎并缓存."""
    engine, _ = create_engine_mock()
    create_engine = MagicMock(
        return_value=engine
    )

    monkeypatch.setattr(
        engine_module,
        "create_engine",
        create_engine,
    )

    first = engine_module.get_engine()
    second = engine_module.get_engine()

    assert first is engine
    assert second is engine
    assert first is second
    assert engine_module._engine is engine
    create_engine.assert_called_once_with()


def test_get_engine_returns_existing_engine(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已有引擎时直接返回."""
    engine, _ = create_engine_mock()
    create_engine = MagicMock()

    engine_module._engine = engine

    monkeypatch.setattr(
        engine_module,
        "create_engine",
        create_engine,
    )

    result = engine_module.get_engine()

    assert result is engine
    create_engine.assert_not_called()


@pytest.mark.asyncio
async def test_dispose_engine_disposes_existing_engine(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试关闭引擎并重置会话工厂."""
    engine, dispose = create_engine_mock()
    reset_session_factory = MagicMock()

    engine_module._engine = engine

    monkeypatch.setattr(
        session_module,
        "reset_session_factory",
        reset_session_factory,
    )

    await engine_module.dispose_engine()

    assert engine_module._engine is None
    reset_session_factory.assert_called_once_with()
    dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_dispose_engine_without_existing_engine(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试无引擎时仍重置会话工厂."""
    reset_session_factory = MagicMock()

    monkeypatch.setattr(
        session_module,
        "reset_session_factory",
        reset_session_factory,
    )

    await engine_module.dispose_engine()

    assert engine_module._engine is None
    reset_session_factory.assert_called_once_with()


@pytest.mark.asyncio
async def test_dispose_engine_clears_state_before_dispose(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试引擎释放失败时全局状态仍已清理."""
    engine, dispose = create_engine_mock()
    reset_session_factory = MagicMock()

    dispose.side_effect = RuntimeError(
        "dispose failed"
    )
    engine_module._engine = engine

    monkeypatch.setattr(
        session_module,
        "reset_session_factory",
        reset_session_factory,
    )

    with pytest.raises(
            RuntimeError,
            match="dispose failed",
    ):
        await engine_module.dispose_engine()

    assert engine_module._engine is None
    reset_session_factory.assert_called_once_with()
    dispose.assert_awaited_once_with()
