"""影子预测任务

定义影子预测执行所需的运行时数据结构。任务调度由 Celery 和独立
Redis Broker 负责，消息中仅传递持久化执行记录 ID。

核心功能：
  - ShadowTask: 已从持久化记录还原的影子预测任务
"""

from dataclasses import dataclass
from typing import Any

from datamind.runtime.executor import ExecutionPlan


@dataclass(slots=True)
class ShadowTask:
    """影子预测任务"""

    execution_id: str
    request_id: str
    decision_id: str
    plan: ExecutionPlan
    features: dict[str, Any]
