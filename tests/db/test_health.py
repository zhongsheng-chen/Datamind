"""数据库健康检查测试

验证数据库健康检查在执行成功、引擎获取失败、
连接失败和 SQL 执行失败时的返回结果与日志行为。

核心功能：
  - test_health_check_success:
    验证数据库健康检查成功
  - test_health_check_engine_error:
    验证获取数据库引擎失败
  - test_health_check_connection_error:
    验证建立数据库连接失败
  - test_health_check_execute_error:
    验证健康检查 SQL 执行失败
  - test_health_check_rounds_latency:
    验证检查耗时保留两位小数
"""

from typing import cast
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
)
from sqlalchemy.sql.elements import TextClause

import datamind.db.health as health_module


def create_health_resources() -> tuple[
    AsyncEngine,
    AsyncConnection,
    MagicMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    """创建健康检查所需的引擎和连接替身"""
    execute = AsyncMock()
    connection = MagicMock(
        spec=AsyncConnection
    )
    connection.execute = execute

    enter = AsyncMock(
        return_value=connection
    )
    exit_context = AsyncMock(
        return_value=False
    )
    connection_context = MagicMock()
    connection_context.__aenter__ = enter
    connection_context.__aexit__ = (
        exit_context
    )

    connect = MagicMock(
        return_value=connection_context
    )
    engine = MagicMock(
        spec=AsyncEngine
    )
    engine.connect = connect

    return (
        cast(
            AsyncEngine,
            cast(
                object,
                engine,
            ),
        ),
        cast(
            AsyncConnection,
            cast(
                object,
                connection,
            ),
        ),
        connect,
        execute,
        enter,
        exit_context,
    )


@pytest.mark.asyncio
async def test_health_check_success(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证数据库健康检查成功"""
    (
        engine,
        connection,
        connect,
        execute,
        enter,
        exit_context,
    ) = create_health_resources()
    get_engine = MagicMock(
        return_value=engine
    )
    perf_counter = MagicMock(
        side_effect=[
            100.0,
            100.01236,
        ]
    )
    logger = MagicMock()
    logger_info = MagicMock()
    logger_error = MagicMock()
    logger.info = logger_info
    logger.error = logger_error

    monkeypatch.setitem(
        vars(health_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setattr(
        health_module.time,
        "perf_counter",
        perf_counter,
    )
    monkeypatch.setattr(
        health_module,
        "logger",
        logger,
    )

    result = await health_module.health_check()

    assert result == {
        "status": "ok",
        "latency_ms": 12.36,
        "error": None,
    }
    get_engine.assert_called_once_with()
    connect.assert_called_once_with()
    enter.assert_awaited_once_with()
    exit_context.assert_awaited_once_with(
        None,
        None,
        None,
    )
    execute.assert_awaited_once()

    awaited_call = execute.await_args

    assert awaited_call is not None

    statement = awaited_call.args[
        0
    ]

    assert isinstance(
        statement,
        TextClause,
    )
    assert str(
        statement
    ) == "SELECT 1"
    enter_awaited_call = enter.await_args
    assert enter_awaited_call is not None

    assert (
        enter_awaited_call.args
        == ()
    )
    assert (
        connection
        is enter.return_value
    )
    logger_info.assert_called_once_with(
        "数据库健康检查通过",
        status="ok",
        latency_ms=12.36,
    )
    logger_error.assert_not_called()
    assert perf_counter.call_count == 2


@pytest.mark.asyncio
async def test_health_check_engine_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证获取数据库引擎失败"""
    get_engine = MagicMock(
        side_effect=RuntimeError(
            "database configuration invalid"
        )
    )
    perf_counter = MagicMock(
        side_effect=[
            10.0,
            10.001,
        ]
    )
    logger = MagicMock()
    logger_info = MagicMock()
    logger_error = MagicMock()
    logger.info = logger_info
    logger.error = logger_error

    monkeypatch.setitem(
        vars(health_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setattr(
        health_module.time,
        "perf_counter",
        perf_counter,
    )
    monkeypatch.setattr(
        health_module,
        "logger",
        logger,
    )

    result = await health_module.health_check()

    assert result == {
        "status": "error",
        "latency_ms": 1.0,
        "error": (
            "database configuration invalid"
        ),
    }
    get_engine.assert_called_once_with()
    logger_info.assert_not_called()
    logger_error.assert_called_once_with(
        "数据库健康检查失败",
        status="error",
        latency_ms=1.0,
        error=(
            "database configuration invalid"
        ),
    )


@pytest.mark.asyncio
async def test_health_check_connection_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证建立数据库连接失败"""
    (
        engine,
        _,
        connect,
        execute,
        enter,
        exit_context,
    ) = create_health_resources()
    enter.side_effect = ConnectionError(
        "database unavailable"
    )
    get_engine = MagicMock(
        return_value=engine
    )
    perf_counter = MagicMock(
        side_effect=[
            20.0,
            20.025,
        ]
    )
    logger = MagicMock()
    logger_info = MagicMock()
    logger_error = MagicMock()
    logger.info = logger_info
    logger.error = logger_error

    monkeypatch.setitem(
        vars(health_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setattr(
        health_module.time,
        "perf_counter",
        perf_counter,
    )
    monkeypatch.setattr(
        health_module,
        "logger",
        logger,
    )

    result = await health_module.health_check()

    assert result == {
        "status": "error",
        "latency_ms": 25.0,
        "error": "database unavailable",
    }
    connect.assert_called_once_with()
    enter.assert_awaited_once_with()
    execute.assert_not_awaited()
    exit_context.assert_not_awaited()
    logger_info.assert_not_called()
    logger_error.assert_called_once_with(
        "数据库健康检查失败",
        status="error",
        latency_ms=25.0,
        error="database unavailable",
    )


@pytest.mark.asyncio
async def test_health_check_execute_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证健康检查 SQL 执行失败"""
    (
        engine,
        _,
        connect,
        execute,
        enter,
        exit_context,
    ) = create_health_resources()
    execute.side_effect = RuntimeError(
        "query failed"
    )
    get_engine = MagicMock(
        return_value=engine
    )
    perf_counter = MagicMock(
        side_effect=[
            30.0,
            30.005,
        ]
    )
    logger = MagicMock()
    logger_info = MagicMock()
    logger_error = MagicMock()
    logger.info = logger_info
    logger.error = logger_error

    monkeypatch.setitem(
        vars(health_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setattr(
        health_module.time,
        "perf_counter",
        perf_counter,
    )
    monkeypatch.setattr(
        health_module,
        "logger",
        logger,
    )

    result = await health_module.health_check()

    assert result == {
        "status": "error",
        "latency_ms": 5.0,
        "error": "query failed",
    }
    connect.assert_called_once_with()
    enter.assert_awaited_once_with()
    execute.assert_awaited_once()
    exit_context.assert_awaited_once()

    exit_call = exit_context.await_args

    assert exit_call is not None
    assert exit_call.args[
        0
    ] is RuntimeError
    assert isinstance(
        exit_call.args[
            1
        ],
        RuntimeError,
    )
    logger_info.assert_not_called()
    logger_error.assert_called_once_with(
        "数据库健康检查失败",
        status="error",
        latency_ms=5.0,
        error="query failed",
    )


@pytest.mark.asyncio
async def test_health_check_rounds_latency(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证检查耗时保留两位小数"""
    (
        engine,
        _,
        _,
        _,
        _,
        _,
    ) = create_health_resources()
    get_engine = MagicMock(
        return_value=engine
    )
    perf_counter = MagicMock(
        side_effect=[
            50.0,
            50.00123456,
        ]
    )
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()

    monkeypatch.setitem(
        vars(health_module),
        "get_engine",
        get_engine,
    )
    monkeypatch.setattr(
        health_module.time,
        "perf_counter",
        perf_counter,
    )
    monkeypatch.setattr(
        health_module,
        "logger",
        logger,
    )

    result = await health_module.health_check()

    assert result[
        "latency_ms"
    ] == 1.23
