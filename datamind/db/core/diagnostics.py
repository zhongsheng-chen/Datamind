# datamind/db/core/diagnostics.py

"""数据库诊断工具

提供数据库连接和连接池的诊断信息。

核心功能：
  - get_db_url_diagnostics: 获取数据库 URL 诊断信息
  - get_db_pool_diagnostics: 获取连接池诊断信息
  - get_db_diagnostics: 获取完整诊断信息
  - log_db_diagnostics: 打印数据库诊断信息

使用示例：
  from datamind.db.core.diagnostics import log_db_diagnostics

  log_db_diagnostics()
"""

import structlog
from sqlalchemy.engine import make_url

from datamind.config import get_settings
from datamind.db.core.engine import get_engine
from datamind.db.core.url import get_db_url

logger = structlog.get_logger(__name__)


def get_db_url_diagnostics() -> dict:
    """获取数据库 URL 诊断信息

    返回：
        包含 driver、host、port、database、username 的字典
    """
    parsed = make_url(str(get_db_url()))

    return {
        "driver": parsed.drivername,
        "host": parsed.host,
        "port": parsed.port,
        "database": parsed.database,
        "username": parsed.username,
    }


def get_db_pool_diagnostics() -> dict:
    """获取连接池诊断信息

    返回：
        包含连接池配置和运行状态的字典

    说明：
        overflow 表示当前连接数减去 pool_size，
        在连接池刚初始化时可能为负数。
    """
    settings = get_settings()
    db = settings.database

    engine = get_engine()
    pool = engine.pool

    return {
        "pool_size": db.pool_size,
        "max_overflow": db.max_overflow,
        "pool_timeout": db.pool_timeout,
        "pool_recycle": db.pool_recycle,

        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }


def get_db_diagnostics() -> dict:
    """获取完整诊断信息

    返回：
        合并 URL 和连接池诊断信息的字典
    """
    return {
        **get_db_url_diagnostics(),
        **get_db_pool_diagnostics(),
    }


def log_db_diagnostics() -> None:
    """打印数据库诊断信息

    将诊断信息以结构化日志形式输出。
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