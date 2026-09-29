"""Redis 真实集成测试.

验证幂等键的原子占用和队列消息的一次性消费语义。

核心功能：
  - test_idempotency_key_rejects_duplicate_claim: 验证重复任务幂等
  - test_queue_consumption_removes_each_message_once: 验证队列消费顺序
"""

from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_idempotency_key_rejects_duplicate_claim(redis_url: str) -> None:
    """测试 NX 幂等键拒绝重复占用."""
    client = Redis.from_url(redis_url, decode_responses=True)
    key = f"datamind:integration:idempotency:{uuid.uuid4().hex}"
    try:
        assert await client.set(key, "claimed", nx=True, ex=60) is True
        assert await client.set(key, "duplicate", nx=True, ex=60) is None
        assert await client.get(key) == "claimed"
    finally:
        await client.delete(key)
        await client.aclose()


@pytest.mark.asyncio
async def test_queue_consumption_removes_each_message_once(redis_url: str) -> None:
    """测试队列消息按顺序且仅消费一次."""
    client = Redis.from_url(redis_url, decode_responses=True)
    key = f"datamind:integration:queue:{uuid.uuid4().hex}"
    try:
        await client.rpush(key, "attempt-1", "attempt-2")
        assert await client.lpop(key) == "attempt-1"
        assert await client.lpop(key) == "attempt-2"
        assert await client.lpop(key) is None
    finally:
        await client.delete(key)
        await client.aclose()
