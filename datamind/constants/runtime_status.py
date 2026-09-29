"""运行实例状态枚举.

集中定义数据库运行状态和查询时派生的健康状态，避免运行时、仓储和服务层
分别维护字符串常量。

核心功能：
  - RuntimeStatus: 数据库存储的运行实例生命周期状态
  - RuntimeHealthStatus: 根据心跳活动派生的健康状态
  - ACTIVE_RUNTIME_STATUSES: 当前运行实例使用的生命周期状态
"""

from enum import Enum
from typing import Final


class RuntimeStatus(str, Enum):
    """数据库存储的运行实例生命周期状态."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"

    def __str__(self) -> str:
        """返回运行状态字符串."""
        return self.value


class RuntimeHealthStatus(str, Enum):
    """查询时派生的运行实例健康状态."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """返回健康状态字符串."""
        return self.value


ACTIVE_RUNTIME_STATUSES: Final[tuple[str, ...]] = (
    RuntimeStatus.STARTING.value,
    RuntimeStatus.RUNNING.value,
    RuntimeStatus.STOPPING.value,
)
