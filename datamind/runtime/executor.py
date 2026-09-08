"""模型预测执行器

统一执行主预测和影子预测，负责加载目标运行时服务、
调用模型并统计执行耗时。

核心功能：
  - execute: 执行模型预测计划
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from datamind.models.enums import ExecutionType
from datamind.runtime.routing import RouteResult
from datamind.runtime.serving.base import BaseRuntimeService


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """单次模型执行计划"""

    route: RouteResult
    execution_type: ExecutionType
    timeout: float | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """单次模型执行结果"""

    plan: ExecutionPlan
    prediction: dict[str, Any]
    latency_ms: float

    @property
    def route(self) -> RouteResult:
        """返回本次执行使用的路由"""
        return self.plan.route


class PredictionExecutor:
    """统一模型预测执行器"""

    def __init__(
            self,
            *,
            service_loader: Callable[
                [str],
                Awaitable[BaseRuntimeService],
            ],
    ) -> None:
        """初始化模型预测执行器"""
        self._service_loader = service_loader

    async def execute(
            self,
            *,
            plan: ExecutionPlan,
            features: dict[str, Any],
    ) -> ExecutionResult:
        """执行单次模型预测计划"""
        started_at = time.perf_counter()
        prediction = await self._predict_with_timeout(
            plan=plan,
            features=features,
        )

        latency_ms = (
                             time.perf_counter()
                             - started_at
                     ) * 1000

        return ExecutionResult(
            plan=plan,
            prediction=prediction,
            latency_ms=latency_ms,
        )

    async def _predict_with_timeout(
            self,
            *,
            plan: ExecutionPlan,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """根据执行计划应用超时并执行预测"""
        if plan.timeout is None:
            return await self._predict(
                plan=plan,
                features=features,
            )

        async with asyncio.timeout(
                plan.timeout
        ):
            return await self._predict(
                plan=plan,
                features=features,
            )

    async def _predict(
            self,
            *,
            plan: ExecutionPlan,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """加载运行时服务并执行模型预测"""
        service = await self._service_loader(
            plan.route.deployment_id
        )

        return await asyncio.to_thread(
            service.predict,
            features,
        )
