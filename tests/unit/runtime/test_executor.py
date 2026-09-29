"""模型预测执行器测试.

验证统一执行器的服务加载、模型调用、结果封装和超时控制。

核心功能：
  - test_execute_loads_service_and_returns_prediction:
    验证执行器加载服务并返回预测结果
  - test_execute_applies_plan_timeout:
    验证执行器应用执行计划的超时限制
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.models.enums import ExecutionType
from datamind.runtime.executor import (
    ExecutionPlan,
    PredictionExecutor,
)
from datamind.runtime.routing import RouteResult


def create_plan(
        *,
        timeout: float | None = None,
) -> ExecutionPlan:
    """创建模型执行计划."""
    return ExecutionPlan(
        route=RouteResult(
            model_id="mdl_test",
            version_id="ver_test",
            deployment_id="dep_test",
            framework="sklearn",
            environment="testing",
            source="deployment",
            strategy="fallback",
        ),
        execution_type=ExecutionType.PRIMARY,
        timeout=timeout,
    )


@pytest.mark.asyncio
async def test_execute_loads_service_and_returns_prediction() -> None:
    """测试执行计划加载服务并返回预测结果."""
    service = MagicMock()
    service.predict.return_value = {
        "score": 720.0,
    }
    service_loader = AsyncMock(
        return_value=service
    )
    executor = PredictionExecutor(
        service_loader=service_loader,
    )
    plan = create_plan()

    result = await executor.execute(
        plan=plan,
        features={"age": 35},
    )

    service_loader.assert_awaited_once_with(
        "dep_test"
    )
    service.predict.assert_called_once_with({
        "age": 35,
    })
    assert result.plan is plan
    assert result.route is plan.route
    assert result.prediction == {
        "score": 720.0,
    }
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_execute_applies_plan_timeout() -> None:
    """测试执行计划应用超时限制."""
    service = MagicMock()

    def predict(_features: dict[str, object]) -> dict[str, object]:
        import time

        time.sleep(0.05)
        return {}

    service.predict.side_effect = predict
    executor = PredictionExecutor(
        service_loader=AsyncMock(
            return_value=service
        ),
    )

    with pytest.raises(TimeoutError):
        await executor.execute(
            plan=create_plan(timeout=0.001),
            features={"age": 35},
        )

    await asyncio.sleep(0.06)
