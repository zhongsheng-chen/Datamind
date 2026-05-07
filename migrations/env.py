# datamind/migrations/env.py

"""Alembic 迁移环境配置

支持异步数据库迁移，使用项目统一配置组件管理数据库连接。

核心功能：
  - run_migrations_offline: 离线模式生成 SQL 脚本
  - run_migrations_online: 在线模式执行迁移
  - get_url: 从配置组件获取数据库连接 URL

使用示例：
  # 设置环境变量
  export DATAMIND_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/dbname"

  # 创建迁移
  alembic revision --autogenerate -m "init schema"

  # 执行迁移
  alembic upgrade head
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import async_engine_from_config

from datamind.config import get_settings
from datamind.db.core import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()


def get_url() -> str:
    """获取数据库连接 URL

    返回：
        数据库连接字符串

    异常：
        ValueError: 未配置数据库 URL
    """
    url = settings.database.url

    if not url:
        raise ValueError(
            "未配置数据库连接 URL，请设置环境变量 DATAMIND_DATABASE_URL"
        )

    return url


config.set_main_option("sqlalchemy.url", get_url())


def run_migrations_offline() -> None:
    """离线模式

    不连接数据库，仅生成 SQL 脚本。
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移核心逻辑

    参数：
        connection: 数据库同步连接
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式

    异步连接数据库并执行迁移。
    """
    connectable: AsyncEngine = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())