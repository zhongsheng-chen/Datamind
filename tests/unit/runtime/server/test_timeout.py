"""请求预算测试.

验证请求预算在处理阶段之间的共享、超时和取消行为。

核心功能：
  - test_budget_is_shared:
    验证跨阶段共用截止时间
  - test_budget_preserves_dependency_timeout:
    验证不改写下游超时
  - test_budget_preserves_cancellation:
    验证不吞掉外部取消
  - test_budget_checks_synchronous_work:
    验证同步处理消耗的预算
"""

import asyncio

import pytest

from datamind.runtime.server.timeout import RequestTimeoutError, request_budget


@pytest.mark.asyncio
async def test_budget_is_shared() -> None:
    """测试切换阶段不会重置请求截止时间."""
    async with request_budget(1) as budget:
        deadline = budget.deadline
        budget.enter_stage("routing")
        await asyncio.sleep(0)
        budget.enter_stage("prediction")
        assert budget.deadline == deadline

    with pytest.raises(RequestTimeoutError) as caught:
        async with request_budget(0.01) as budget:
            budget.enter_stage("prediction")
            await asyncio.Event().wait()
    assert caught.value.stage == "prediction"
    assert caught.value.seconds == 0.01


@pytest.mark.asyncio
async def test_budget_preserves_dependency_timeout() -> None:
    """测试预算未耗尽时保留下游原始异常."""
    failure = TimeoutError("database timeout")
    with pytest.raises(TimeoutError) as caught:
        async with request_budget(1):
            raise failure
    assert caught.value is failure


@pytest.mark.asyncio
async def test_budget_preserves_cancellation() -> None:
    """测试外部取消不伪装成请求超时."""
    with pytest.raises(asyncio.CancelledError):
        async with request_budget(1):
            raise asyncio.CancelledError


@pytest.mark.asyncio
async def test_budget_checks_synchronous_work() -> None:
    """测试没有异步切换时也不能进入已经过期的下一阶段."""
    with pytest.raises(RequestTimeoutError) as caught:
        async with request_budget(0) as budget:
            budget.enter_stage("persistence")
    assert caught.value.stage == "request"
