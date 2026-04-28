"""数据库引擎管理

提供异步数据库引擎的创建和单例管理。

核心功能：
  - create_engine: 创建异步数据库引擎
  - get_engine: 获取数据库引擎实例

使用示例：
  from datamind.db.core.engine import get_engine

  engine = get_engine()
"""

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from datamind.config import get_settings
from datamind.logging import get_logger
from datamind.db.core.url import get_db_url

logger = get_logger(__name__)

_engine: AsyncEngine | None = None


def create_engine() -> AsyncEngine:
    """创建异步数据库引擎

    返回：
        AsyncEngine 实例
    """
    settings = get_settings()
    db = settings.database
    url = get_db_url()

    logger.info("创建数据库引擎...")
    logger.debug(
        "数据库连接池配置",
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout,
        pool_recycle=db.pool_recycle,
        echo=db.echo,
    )

    engine = create_async_engine(
        url,
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout,
        pool_recycle=db.pool_recycle,
        echo=db.echo,
        pool_pre_ping=True,
        future=True,
        connect_args={
            "statement_cache_size": 0,
        },
    )

    logger.info(
        "创建数据库引擎成功",
        url=make_url(url).render_as_string(hide_password=True),
    )

    return engine


def get_engine() -> AsyncEngine:
    """获取数据库引擎实例

    返回：
        AsyncEngine 实例
    """
    global _engine

    if _engine is None:
        _engine = create_engine()

    return _engine