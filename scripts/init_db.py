# scripts/init_db.py

"""数据库初始化脚本

执行数据库迁移。

核心功能：
  - init_database: 执行数据库迁移

使用示例：
  python scripts/init_db.py
"""

import structlog

from datamind.db import run_migrations

logger = structlog.get_logger(__name__)


def init_database():
    """初始化数据库

    执行 Alembic 迁移。
    """
    try:
        logger.info("开始初始化数据库")

        run_migrations()

        logger.info("数据库初始化完成")

    except Exception as e:
        logger.error(
            "数据库初始化失败",
            error=str(e),
            exc_info=True,
        )
        raise


if __name__ == "__main__":
    init_database()