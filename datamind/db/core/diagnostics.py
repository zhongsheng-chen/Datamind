"""数据库诊断工具

提供数据库连接配置和连接池运行状态的诊断信息。

核心功能：
  - get_db_url_diagnostics: 获取数据库 URL 诊断信息
  - get_db_pool_diagnostics: 获取数据库连接池诊断信息
  - get_db_diagnostics: 获取完整数据库诊断信息
  - log_db_diagnostics: 记录数据库诊断信息

使用示例：
  from datamind.db.core.diagnostics import log_db_diagnostics

  log_db_diagnostics()
"""

import structlog
from sqlalchemy.engine import make_url
from sqlalchemy.pool import QueuePool

from datamind.config import get_database_config
from datamind.db.core.engine import get_engine
from datamind.db.core.url import get_db_url


logger = structlog.get_logger(__name__)


def _get_queue_pool() -> QueuePool:
    """获取队列连接池

    返回：
        QueuePool 实例

    异常：
        RuntimeError: 当前引擎未使用队列连接池
    """
    pool = get_engine().pool

    if not isinstance(
        pool,
        QueuePool,
    ):
        raise RuntimeError(
            "当前数据库引擎未使用队列连接池，"
            f"实际类型：{type(pool).__name__}"
        )

    return pool


def get_db_url_diagnostics(
) -> dict[str, str | int | None]:
    """获取数据库 URL 诊断信息

    不返回数据库密码。

    返回：
        包含 driver、host、port、database 和 username 的字典
    """
    parsed = make_url(
        get_db_url()
    )

    return {
        "driver": parsed.drivername,
        "host": parsed.host,
        "port": parsed.port,
        "database": parsed.database,
        "username": parsed.username,
    }


def get_db_pool_diagnostics(
) -> dict[str, int]:
    """获取数据库连接池诊断信息

    返回：
        包含连接池配置和运行状态的字典

    说明：
        overflow 表示当前溢出连接数量，
        连接池刚初始化时可能为负数。
    """
    db = get_database_config()

    pool = _get_queue_pool()

    return {
        "pool_size": db.pool_size,
        "max_overflow": db.max_overflow,
        "pool_timeout": db.pool_timeout,
        "pool_recycle": db.pool_recycle,
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }


def get_db_diagnostics(
) -> dict[str, str | int | None]:
    """获取完整数据库诊断信息

    返回：
        合并数据库 URL 和连接池诊断信息的字典
    """
    return {
        **get_db_url_diagnostics(),
        **get_db_pool_diagnostics(),
    }


def log_db_diagnostics(
) -> None:
    """记录数据库诊断信息

    获取失败时继续向上抛出异常，
    避免掩盖数据库配置或引擎初始化问题。
    """
    info = get_db_diagnostics()

    logger.info(
        "数据库配置",
        driver=info["driver"],
        host=info["host"],
        port=info["port"],
        database=info["database"],
        username=info["username"],
        pool_size=info["pool_size"],
        max_overflow=info["max_overflow"],
        pool_timeout=info["pool_timeout"],
        pool_recycle=info["pool_recycle"],
        checked_in=info["checked_in"],
        checked_out=info["checked_out"],
        overflow=info["overflow"],
    )
