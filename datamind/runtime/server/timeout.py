"""预测请求时间预算

统一管理单条和批量预测请求的截止时间，
记录处理阶段并将预算耗尽转换为请求超时异常。

核心功能：
  - RequestBudget: 在各处理阶段之间共享截止时间
  - enter_stage: 检查剩余时间并切换处理阶段
  - request_budget: 将预算耗尽转换为明确的请求超时异常
  - RequestTimeoutError: 携带超时阶段及配置时限

使用示例：
  from datamind.runtime.server.timeout import request_budget

  async with request_budget(seconds=30) as budget:
      budget.enter_stage("prediction")
      result = await predict(features)
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


# 请求超时后的收尾宽限时间（秒）
REQUEST_TIMEOUT_GRACE_SECONDS = 5


class RequestTimeoutError(RuntimeError):
    """预测请求处理预算耗尽"""

    def __init__(self, seconds: float, stage: str) -> None:
        """初始化请求超时异常

        参数：
            seconds: 请求超时时间（秒）
            stage: 超时发生时的处理阶段
        """
        self.seconds = seconds
        self.stage = stage
        super().__init__(
            f"预测请求处理超时（限制 {seconds:g} 秒，阶段 {stage}）"
        )


@dataclass
class RequestBudget:
    """请求时间预算

    属性：
        seconds: 请求超时时间（秒）
        deadline: 基于事件循环单调时钟的截止时间
        stage: 当前处理阶段
    """

    seconds: float
    deadline: float
    stage: str = "request"

    def enter_stage(self, stage: str) -> None:
        """检查剩余时间并切换处理阶段

        参数：
            stage: 下一处理阶段

        异常：
            RequestTimeoutError: 请求已到达截止时间
        """
        if asyncio.get_running_loop().time() >= self.deadline:
            raise RequestTimeoutError(self.seconds, self.stage)
        self.stage = stage


@asynccontextmanager
async def request_budget(seconds: float) -> AsyncIterator[RequestBudget]:
    """建立共享截止时间的请求作用域

    路由、模型加载、预测及结果保存共享同一预算。
    下游自身的超时和外部取消保持原始异常，不转换为请求超时。

    参数：
        seconds: 请求超时时间（秒）

    返回：
        提供 RequestBudget 的异步上下文管理器

    异常：
        RequestTimeoutError: 请求处理预算耗尽

    注意：
        - 服务层负责将请求超时转换为 HTTP 504
        - REQUEST_TIMEOUT_GRACE_SECONDS 为失败记录提供额外收尾时间
        - HTTP 层以请求预算加收尾预算兜底，其时限包含认证耗时
        - 影子预测使用独立预算，取消等待不会终止已运行的同步模型线程
        - 已开始提交的事务可能继续安全收尾，超时不代表事务未提交
    """
    budget = RequestBudget(
        seconds=seconds,
        deadline=asyncio.get_running_loop().time() + seconds,
    )
    timer = asyncio.timeout_at(budget.deadline)
    try:
        async with timer:
            yield budget
            budget.enter_stage("response")
    except TimeoutError as exc:
        if not timer.expired():
            raise
        raise RequestTimeoutError(seconds, budget.stage) from exc
