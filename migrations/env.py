# Datamind/migrations/env.py
"""Alembic 环境配置文件

负责：
 - 设置数据库连接
 - 加载数据库模型
 - 配置迁移运行环境
"""

from alembic import context
from sqlalchemy import pool
from sqlalchemy import engine_from_config
from logging.config import fileConfig

from datamind.config.settings import get_settings
from datamind.core.db import models
from datamind.core.db import Base

# 获取配置实例
settings = get_settings()

# 获取 Alembic 配置对象（来自 alembic.ini）
config = context.config

# 从项目配置中获取数据库 URL，覆盖 alembic.ini 中的配置
db_url = settings.database.url
if db_url.startswith("postgresql+asyncpg"):
    db_url = db_url.replace("postgresql+asyncpg", "postgresql")
config.set_main_option("sqlalchemy.url", db_url)


# 设置日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
# Alembic 通过比较 target_metadata 和数据库当前状态来生成迁移脚本
# Base.metadata 包含了所有通过 SQLAlchemy 定义的模型
target_metadata = Base.metadata

# 可以添加调试信息（可选）
if settings.app.debug:
    print(f"数据库连接: {settings.database.url}")
    print(f"环境: {settings.app.env}")
    print(f"调试模式: {settings.app.debug}")


def run_migrations_offline() -> None:
    """
    离线模式运行迁移

    在这种模式下，Alembic 不会连接数据库，而是生成 SQL 脚本。
    适用于：
    - 生成迁移脚本供审查
    - 在无法直接连接数据库的环境中使用
    - 生产环境手动执行迁移前预览 SQL
    """
    url = config.get_main_option("sqlalchemy.url")

    # 配置离线迁移上下文
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,                    # 使用字面值绑定参数，生成可读的 SQL
        dialect_opts={"paramstyle": "named"},  # 使用命名参数风格
        compare_type=True,                     # 比较列类型变化
        compare_server_default=True,           # 比较默认值变化
        include_schemas=True,                  # 包含 schema（如 public）
        version_table_schema='public'          # 版本表存储在 public schema 中
    )

    # 开始事务并运行迁移
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式运行迁移

    这种模式下，Alembic 直接连接数据库执行迁移。
    适用于：
    - 开发环境自动迁移
    - 测试环境自动迁移
    - 需要实际执行迁移的场景
    """

    # 获取数据库连接
    # 优先使用已经存在的连接（如从外部传入）
    connectable = context.config.attributes.get("connection", None)

    if connectable is None:
        # 如果没有现有连接，则创建新的数据库引擎
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,  # 迁移时不使用连接池
        )

    # 建立连接并运行迁移
    with connectable.connect() as connection:
        # 配置在线迁移上下文
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,                # 比较列类型变化
            compare_server_default=True,      # 比较默认值变化
            include_schemas=True,             # 包含 schema
            version_table_schema='public'     # 版本表存储在 public schema 中
        )

        # 开始事务并运行迁移
        with context.begin_transaction():
            context.run_migrations()


# 根据 Alembic 的运行模式选择相应的函数
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()