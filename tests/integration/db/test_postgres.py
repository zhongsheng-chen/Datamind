"""PostgreSQL 真实集成测试

验证真实数据库的事务回滚、唯一约束、外键约束和 Outbox JSONB 载荷。

核心功能：
  - test_transaction_rollback_is_visible_to_a_new_transaction: 验证事务回滚
  - test_committed_lifecycle_state_is_visible_to_a_new_connection: 验证状态持久化
  - test_unique_and_foreign_key_constraints_are_enforced: 验证数据库约束
  - test_outbox_payload_round_trips_as_jsonb: 验证 Outbox 载荷持久化
"""

from __future__ import annotations

import json
import uuid

import asyncpg
import pytest


pytestmark = pytest.mark.integration


def _asyncpg_url(database_url: str) -> str:
    """返回 asyncpg 原生连接可接受的测试数据库地址"""
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql://",
        1,
    )


@pytest.mark.asyncio
async def test_transaction_rollback_is_visible_to_a_new_transaction(
    database_url: str,
) -> None:
    """测试回滚后事务写入不可见"""
    connection = await asyncpg.connect(_asyncpg_url(database_url))
    table = f"dm_it_rollback_{uuid.uuid4().hex}"
    try:
        await connection.execute(
            f'CREATE TEMP TABLE "{table}" (value INTEGER NOT NULL)'
        )
        transaction = connection.transaction()
        await transaction.start()
        await connection.execute(f'INSERT INTO "{table}" VALUES (1)')
        await transaction.rollback()
        assert await connection.fetchval(f'SELECT COUNT(*) FROM "{table}"') == 0
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_committed_lifecycle_state_is_visible_to_a_new_connection(
    database_url: str,
) -> None:
    """测试提交后的生命周期状态可被新连接读取"""
    table = f"dm_it_lifecycle_{uuid.uuid4().hex}"
    native_url = _asyncpg_url(database_url)
    writer = await asyncpg.connect(native_url)
    try:
        await writer.execute(
            f'CREATE TABLE "{table}" ('
            "resource_id TEXT PRIMARY KEY, status TEXT NOT NULL)"
        )
        await writer.execute(
            f'INSERT INTO "{table}" (resource_id, status) VALUES ($1, $2)',
            "mdl_integration",
            "registered",
        )
        await writer.execute(
            f'UPDATE "{table}" SET status = $1 WHERE resource_id = $2',
            "active",
            "mdl_integration",
        )

        reader = await asyncpg.connect(native_url)
        try:
            stored = await reader.fetchval(
                f'SELECT status FROM "{table}" WHERE resource_id = $1',
                "mdl_integration",
            )
        finally:
            await reader.close()

        assert stored == "active"
    finally:
        await writer.execute(f'DROP TABLE IF EXISTS "{table}"')
        await writer.close()


@pytest.mark.asyncio
async def test_unique_and_foreign_key_constraints_are_enforced(
    database_url: str,
) -> None:
    """测试真实 PostgreSQL 强制执行唯一约束和外键约束"""
    connection = await asyncpg.connect(_asyncpg_url(database_url))
    suffix = uuid.uuid4().hex
    parent = f"dm_it_parent_{suffix}"
    child = f"dm_it_child_{suffix}"
    try:
        await connection.execute(
            f'CREATE TEMP TABLE "{parent}" (id INTEGER PRIMARY KEY)'
        )
        await connection.execute(
            f'CREATE TEMP TABLE "{child}" ('
            f'id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES "{parent}"(id))'
        )
        await connection.execute(f'INSERT INTO "{parent}" VALUES (1)')
        with pytest.raises(asyncpg.UniqueViolationError):
            await connection.execute(f'INSERT INTO "{parent}" VALUES (1)')
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await connection.execute(f'INSERT INTO "{child}" VALUES (1, 999)')
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_outbox_payload_round_trips_as_jsonb(database_url: str) -> None:
    """测试 Outbox JSONB 载荷可无损写入和读取"""
    connection = await asyncpg.connect(_asyncpg_url(database_url))
    table = f"dm_it_outbox_{uuid.uuid4().hex}"
    payload = {"model_id": "mdl_integration", "status": "active"}
    try:
        await connection.execute(
            f'CREATE TEMP TABLE "{table}" (payload JSONB NOT NULL)'
        )
        await connection.execute(
            f'INSERT INTO "{table}" (payload) VALUES ($1::jsonb)', json.dumps(payload)
        )
        stored = await connection.fetchval(f'SELECT payload FROM "{table}"')
        assert json.loads(stored) == payload
    finally:
        await connection.close()
