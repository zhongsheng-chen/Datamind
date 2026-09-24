"""后端 E2E 测试公共配置.

提供复用集成测试数据库的后端 E2E 夹具。

核心功能：
  - database_url: 返回 PostgreSQL 测试数据库地址
  - datamind_database: 创建测试独享的数据库 Schema
"""

from tests.integration.conftest import (
    database_url,
    datamind_database,
)


__all__ = (
    "database_url",
    "datamind_database",
)
