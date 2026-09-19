"""集成测试公共配置

提供隔离的集成测试基础设施配置。

注意：
  缺少连接配置时自动跳过相关测试。

核心功能：
  - required_test_environment: 读取专用测试环境变量
  - database_url: 返回 PostgreSQL 测试数据库地址
  - redis_url: 返回 Redis 集成测试地址
  - datamind_database: 创建测试独享的数据库 Schema
  - minio_settings: 返回 MinIO 集成测试配置
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from datamind.config.storage import MinIOStorageConfig
from datamind.db.core import Base
from datamind.db.core import engine as engine_module
from datamind.db.core.engine import dispose_engine
from datamind.db.core.session import reset_session_factory

# 确保所有 ORM 表均已注册到 Base.metadata。
from datamind.db import models as _models  # noqa: F401


def required_test_environment(name: str) -> str:
    """读取专用测试环境变量，缺失时给出可操作的跳过原因"""
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


@pytest.fixture
def database_url() -> str:
    """返回 SQLAlchemy asyncpg 测试数据库地址"""
    return required_test_environment(
        "DATAMIND_TEST_DATABASE_URL"
    )


@pytest.fixture
def redis_url() -> str:
    """返回隔离的 Redis 集成测试地址"""
    return required_test_environment("DATAMIND_TEST_REDIS_URL")


@pytest.fixture
async def datamind_database(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncEngine]:
    """在专用 PostgreSQL 中创建每个测试独享的 Datamind schema"""
    schema = f"datamind_it_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(database_url)

    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    application_engine = create_async_engine(
        database_url,
        connect_args={
            "server_settings": {
                "search_path": schema,
            }
        },
    )

    await dispose_engine()
    monkeypatch.setitem(vars(engine_module), "_engine", application_engine)
    reset_session_factory()

    async with application_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield application_engine
    finally:
        reset_session_factory()
        monkeypatch.setitem(vars(engine_module), "_engine", None)
        await application_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


@pytest.fixture
def minio_settings() -> MinIOStorageConfig:
    """返回 MinIO 集成测试凭据与可清理存储桶"""
    return MinIOStorageConfig(
        endpoint=required_test_environment("DATAMIND_TEST_MINIO_ENDPOINT"),
        access_key=required_test_environment("DATAMIND_TEST_MINIO_ACCESS_KEY"),
        secret_key=required_test_environment("DATAMIND_TEST_MINIO_SECRET_KEY"),
        bucket=required_test_environment("DATAMIND_TEST_MINIO_BUCKET"),
        secure=required_test_environment("DATAMIND_TEST_MINIO_SECURE").lower()
        == "true",
    )
