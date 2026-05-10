# scripts/init_db.py

"""数据库初始化脚本

负责执行数据库迁移，初始化数据库表结构。

核心功能：
  - init_database: 执行数据库迁移

使用示例：
  python scripts/init_db.py
"""

import structlog

from datamind.db.migration import run_migrations

logger = structlog.get_logger(__name__)


def init_database():
    """执行数据库迁移

    参数：
        logger: 日志实例
    """
    logger.info("开始初始化数据库")

    run_migrations()

    logger.info("数据库初始化完成")


def main():
    """脚本入口函数"""
    try:
        init_database()

    except Exception as e:
        logger.error(
            "数据库初始化失败",
            error=str(e),
            exc_info=True,
        )
        raise


if __name__ == "__main__":
    main()