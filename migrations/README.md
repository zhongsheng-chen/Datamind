# Datamind 数据库迁移组件

基于 Alembic 的数据库迁移管理，提供版本控制、自动迁移、回滚等功能。

## 特性

- **版本控制** - 每个迁移都有唯一版本号
- **自动生成** - 自动检测模型变化生成迁移脚本
- **双向迁移** - 支持升级和降级
- **多环境支持** - 开发、测试、生产环境独立管理
- **数据完整性** - 确保迁移过程数据安全
- **枚举类型** - 支持 PostgreSQL 枚举类型
- **审计跟踪** - 记录所有迁移操作

## 目录结构
```text
migrations/
├── init.py # 模块初始化
├── cript.py.mako # 迁移脚本模板
├── env.py # Alembic 环境配置
├── alembic.ini # Alembic 配置文件
│── versions # 迁移版本目录
│      ├── 20240315_initial.py # 初始迁移
│      ├── 20240316_add_enums.py # 添加枚举类型
│      ├── 20240317_add_indexes.py # 添加索引
│      ├── 20240318_add_partitions.py # 添加分区表
│      └── 20240319_update_models.py # 更新模型
└── README.md
```


## 快速开始

### 1. 配置数据库连接

编辑 `alembic.ini` 文件，修改数据库连接字符串：

```ini
sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/datamind
```

或者在 env.py 中从环境变量读取：

```bash
# env.py 中会自动从 settings 获取数据库 URL
from config.settings import settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
```

### 2. 创建迁移

```bash
# 自动生成迁移（基于模型变化）
alembic revision --autogenerate -m "添加新表"

# 手动创建空迁移
alembic revision -m "手动迁移"
```

### 3. 执行迁移

```bash
# 升级到最新版本
python -m alembic upgrade head

# 升级到指定版本
python -m alembic upgrade 20240315_initial

# 查看当前版本
python -m alembic current

# 查看历史版本
python -m alembic history
```

### 4. 回滚迁移

```bash
# 回滚一个版本
python -m alembic downgrade -1

# 回滚到指定版本
python -m alembic downgrade 20240315_initial

# 回滚到基础版本
python -m alembic downgrade base

# 
python -m alembic revision --autogenerate -m "test"
python -m alembic upgrade head
```

## 配置文件详解

### alembic.ini

```ini
# migrations/alembic.ini
[alembic]
# 迁移脚本路径
script_location = migrations

# 模板文件
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s

# 时区
timezone = UTC

# 数据库连接
sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/datamind

# 日志配置
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### 环境配置

```python
# datamind/migrations/env.py
import asyncio
import os
import sys
from pathlib import Path
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from logging.config import fileConfig

from datamind.config import get_settings
from datamind.core import Base
from datamind.core import (
    TaskType, ModelType, Framework, ModelStatus,
    AuditAction, DeploymentEnvironment, ABTestStatus
)

# 获取配置实例
settings = get_settings()

# 获取 Alembic 配置对象（来自 alembic.ini）
config = context.config

# 从项目配置中获取数据库 URL，覆盖 alembic.ini 中的配置
config.set_main_option("sqlalchemy.url", settings.database.url)

# 设置日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
target_metadata = Base.metadata

# 可以添加调试信息（可选）
if settings.app.debug:
    print(f"数据库连接: {settings.database.url}")
    print(f"环境: {settings.app.env}")
    print(f"调试模式: {settings.app.debug}")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    # 配置离线迁移上下文
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,  # 使用字面值绑定参数，生成可读的 SQL
        dialect_opts={"paramstyle": "named"},  # 使用命名参数风格
        compare_type=True,  # 比较列类型变化
        compare_server_default=True,  # 比较默认值变化
        include_schemas=True,  # 包含 schema（如 public）
        version_table_schema='public'  # 版本表存储在 public schema 中
    )

    # 开始事务并运行迁移
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection", None)

    if connectable is None:
        # 如果没有现有连接，则创建新的数据库引擎
        connectable = async_engine_from_config(
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
            compare_type=True,  # 比较列类型变化
            compare_server_default=True,  # 比较默认值变化
            include_schemas=True,  # 包含 schema
            version_table_schema='public'  # 版本表存储在 public schema 中
        )

        # 开始事务并运行迁移
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```