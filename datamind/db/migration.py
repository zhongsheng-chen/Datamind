# datamind/db/migration.py

"""数据库迁移模块

负责执行 Alembic 数据库迁移。

核心功能：
  - run_migrations: 执行数据库迁移

使用示例：
  from datamind.db.migration import run_migrations

  run_migrations()
"""

import structlog
from alembic.config import Config
from alembic import command
from alembic.util.exc import CommandError

from datamind import PROJECT_ROOT
from datamind.db.core.url import get_db_url

logger = structlog.get_logger(__name__)

ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
MIGRATIONS = PROJECT_ROOT / "migrations"

def run_migrations(target: str = "head") -> None:
    """执行 Alembic 迁移

    参数：
        target: 迁移目标版本，默认 head
    """
    try:
        logger.info("开始执行数据库迁移", target=target)

        cfg = Config(str(ALEMBIC_INI))

        cfg.set_main_option("sqlalchemy.url", get_db_url())
        cfg.set_main_option("script_location", str(MIGRATIONS))

        command.upgrade(cfg, target)

        logger.info("数据库迁移执行完成", target=target)

    except CommandError as e:
        logger.error("数据库迁移命令失败", error=str(e), target=target)
        raise RuntimeError(f"数据库迁移失败: {e}") from e

    except Exception as e:
        logger.exception("数据库迁移发生未知错误", target=target)
        raise RuntimeError(f"数据库迁移异常: {e}") from e