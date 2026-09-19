"""数据库诊断工具测试

验证数据库 URL 解析、连接池类型检查、连接池状态汇总、
完整诊断信息合并和结构化日志输出。

核心功能：
  - test_get_queue_pool_returns_queue_pool:
    验证获取队列连接池
  - test_get_queue_pool_rejects_unsupported_pool:
    验证拒绝非队列连接池
  - test_get_db_url_diagnostics:
    验证数据库 URL 解析且不泄露密码
  - test_get_db_url_diagnostics_supports_missing_optional_fields:
    验证数据库 URL 可省略可选字段
  - test_get_db_pool_diagnostics:
    验证连接池配置和运行状态
  - test_get_db_pool_diagnostics_preserves_negative_overflow:
    验证保留连接池负溢出值
  - test_get_db_diagnostics:
    验证 URL 与连接池诊断信息合并
  - test_log_db_diagnostics:
    验证结构化日志内容
  - test_log_db_diagnostics_propagates_error:
    验证诊断失败时异常继续向上抛出
"""

from types import SimpleNamespace
from typing import (
    Any,
    cast,
)
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import (
    NullPool,
    QueuePool,
)

import datamind.db.core.diagnostics as diagnostics_module


DATABASE_URL = (
    "postgresql+asyncpg://"
    "datamind:super-secret@db.example.com:5432/datamind"
)


def create_dbapi_connection() -> Any:
    """创建连接池所需的数据库连接替身"""
    return MagicMock()


class DiagnosticsQueuePool(
    QueuePool
):
    """用于诊断测试的队列连接池"""

    def __init__(
            self,
            *,
            checked_in: int,
            checked_out: int,
            overflow: int,
    ) -> None:
        """初始化测试连接池状态"""
        super().__init__(
            creator=create_dbapi_connection,
            pool_size=10,
            max_overflow=20,
        )
        self._diagnostic_checked_in = (
            checked_in
        )
        self._diagnostic_checked_out = (
            checked_out
        )
        self._diagnostic_overflow = overflow

    def checkedin(
            self,
    ) -> int:
        """返回池内连接数"""
        return self._diagnostic_checked_in

    def checkedout(
            self,
    ) -> int:
        """返回已借出连接数"""
        return self._diagnostic_checked_out

    def overflow(
            self,
    ) -> int:
        """返回溢出连接数"""
        return self._diagnostic_overflow


def create_engine_with_pool(
        pool: object,
) -> AsyncEngine:
    """创建包含指定连接池的引擎替身"""
    engine = SimpleNamespace(
        pool=pool
    )

    return cast(
        AsyncEngine,
        cast(
            object,
            engine,
        ),
    )


def test_get_queue_pool_returns_queue_pool(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试获取队列连接池"""
    pool = DiagnosticsQueuePool(
        checked_in=8,
        checked_out=2,
        overflow=0,
    )
    engine = create_engine_with_pool(
        pool
    )
    get_engine = MagicMock(
        return_value=engine
    )

    monkeypatch.setitem(
        vars(diagnostics_module),
        "get_engine",
        get_engine,
    )

    result = diagnostics_module._get_queue_pool()

    assert result is pool
    get_engine.assert_called_once_with()


def test_get_queue_pool_rejects_unsupported_pool(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝非队列连接池"""
    pool = NullPool(
        creator=create_dbapi_connection
    )
    engine = create_engine_with_pool(
        pool
    )
    get_engine = MagicMock(
        return_value=engine
    )

    monkeypatch.setitem(
        vars(diagnostics_module),
        "get_engine",
        get_engine,
    )

    with pytest.raises(
            RuntimeError,
            match=(
                "当前数据库引擎未使用队列连接池，"
                "实际类型：NullPool"
            ),
    ):
        diagnostics_module._get_queue_pool()

    get_engine.assert_called_once_with()


def test_get_db_url_diagnostics(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库 URL 解析且不泄露密码"""
    get_db_url = MagicMock(
        return_value=DATABASE_URL
    )

    monkeypatch.setitem(
        vars(diagnostics_module),
        "get_db_url",
        get_db_url,
    )

    result = (
        diagnostics_module
        .get_db_url_diagnostics()
    )

    assert result == {
        "driver": "postgresql+asyncpg",
        "host": "db.example.com",
        "port": 5432,
        "database": "datamind",
        "username": "datamind",
    }
    assert "password" not in result
    assert "super-secret" not in str(
        result
    )
    get_db_url.assert_called_once_with()


def test_get_db_url_diagnostics_supports_missing_optional_fields(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库 URL 可缺少主机、端口和用户名"""
    get_db_url = MagicMock(
        return_value=(
            "sqlite+aiosqlite:///datamind.db"
        )
    )

    monkeypatch.setitem(
        vars(diagnostics_module),
        "get_db_url",
        get_db_url,
    )

    result = (
        diagnostics_module
        .get_db_url_diagnostics()
    )

    assert result == {
        "driver": "sqlite+aiosqlite",
        "host": None,
        "port": None,
        "database": "datamind.db",
        "username": None,
    }


def test_get_db_pool_diagnostics(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试连接池配置和运行状态"""
    pool = DiagnosticsQueuePool(
        checked_in=7,
        checked_out=3,
        overflow=2,
    )
    database_config = SimpleNamespace(
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )
    get_database_config = MagicMock(
        return_value=database_config
    )
    get_queue_pool = MagicMock(
        return_value=pool
    )

    monkeypatch.setitem(
        vars(diagnostics_module),
        "get_database_config",
        get_database_config,
    )
    monkeypatch.setattr(
        diagnostics_module,
        "_get_queue_pool",
        get_queue_pool,
    )

    result = (
        diagnostics_module
        .get_db_pool_diagnostics()
    )

    assert result == {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "checked_in": 7,
        "checked_out": 3,
        "overflow": 2,
    }
    get_database_config.assert_called_once_with()
    get_queue_pool.assert_called_once_with()


def test_get_db_pool_diagnostics_preserves_negative_overflow(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试连接池初始化阶段的负溢出值不会被修改"""
    pool = DiagnosticsQueuePool(
        checked_in=0,
        checked_out=0,
        overflow=-10,
    )
    database_config = SimpleNamespace(
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )
    monkeypatch.setitem(
        vars(diagnostics_module),
        "get_database_config",
        MagicMock(
            return_value=database_config
        ),
    )
    monkeypatch.setattr(
        diagnostics_module,
        "_get_queue_pool",
        MagicMock(
            return_value=pool
        ),
    )

    result = (
        diagnostics_module
        .get_db_pool_diagnostics()
    )

    assert result["overflow"] == -10


def test_get_db_diagnostics(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 URL 与连接池诊断信息合并"""
    url_diagnostics = {
        "driver": "postgresql+asyncpg",
        "host": "db.example.com",
        "port": 5432,
        "database": "datamind",
        "username": "datamind",
    }
    pool_diagnostics = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "checked_in": 7,
        "checked_out": 3,
        "overflow": 2,
    }
    get_db_url_diagnostics = MagicMock(
        return_value=url_diagnostics
    )
    get_db_pool_diagnostics = MagicMock(
        return_value=pool_diagnostics
    )

    monkeypatch.setattr(
        diagnostics_module,
        "get_db_url_diagnostics",
        get_db_url_diagnostics,
    )
    monkeypatch.setattr(
        diagnostics_module,
        "get_db_pool_diagnostics",
        get_db_pool_diagnostics,
    )

    result = (
        diagnostics_module
        .get_db_diagnostics()
    )

    assert result == {
        **url_diagnostics,
        **pool_diagnostics,
    }
    get_db_url_diagnostics.assert_called_once_with()
    get_db_pool_diagnostics.assert_called_once_with()


def test_log_db_diagnostics(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试结构化日志内容"""
    diagnostics = {
        "driver": "postgresql+asyncpg",
        "host": "db.example.com",
        "port": 5432,
        "database": "datamind",
        "username": "datamind",
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "checked_in": 7,
        "checked_out": 3,
        "overflow": 2,
    }
    get_db_diagnostics = MagicMock(
        return_value=diagnostics
    )
    logger = MagicMock()
    logger_info = MagicMock()
    logger.info = logger_info

    monkeypatch.setattr(
        diagnostics_module,
        "get_db_diagnostics",
        get_db_diagnostics,
    )
    monkeypatch.setattr(
        diagnostics_module,
        "logger",
        logger,
    )

    diagnostics_module.log_db_diagnostics()

    get_db_diagnostics.assert_called_once_with()
    logger_info.assert_called_once_with(
        "数据库配置",
        driver="postgresql+asyncpg",
        host="db.example.com",
        port=5432,
        database="datamind",
        username="datamind",
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        checked_in=7,
        checked_out=3,
        overflow=2,
    )


def test_log_db_diagnostics_propagates_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试诊断失败时异常继续向上抛出"""
    get_db_diagnostics = MagicMock(
        side_effect=RuntimeError(
            "diagnostics failed"
        )
    )
    logger = MagicMock()
    logger_info = MagicMock()
    logger.info = logger_info

    monkeypatch.setattr(
        diagnostics_module,
        "get_db_diagnostics",
        get_db_diagnostics,
    )
    monkeypatch.setattr(
        diagnostics_module,
        "logger",
        logger,
    )

    with pytest.raises(
            RuntimeError,
            match="diagnostics failed",
    ):
        diagnostics_module.log_db_diagnostics()

    get_db_diagnostics.assert_called_once_with()
    logger_info.assert_not_called()
