"""运行实例状态枚举测试.

验证持久化运行状态、派生健康状态和当前实例状态集合保持一致。

核心功能：
  - 验证 RuntimeStatus 的数据库状态值
  - 验证 RuntimeHealthStatus 的派生状态值
  - 验证 ACTIVE_RUNTIME_STATUSES 仅包含当前实例状态
  - test_runtime_status_values:
    测试数据库运行状态枚举值
  - test_runtime_health_status_values:
    测试派生健康状态枚举值
  - test_active_runtime_statuses:
    测试当前实例只包含加载中和已加载状态
"""

from datamind.constants.runtime_status import (
    ACTIVE_RUNTIME_STATUSES,
    RuntimeHealthStatus,
    RuntimeStatus,
)


def test_runtime_status_values() -> None:
    """测试数据库运行状态枚举值."""
    assert tuple(
        status.value
        for status in RuntimeStatus
    ) == (
        "starting",
        "running",
        "stopping",
        "stopped",
        "failed",
    )


def test_runtime_health_status_values() -> None:
    """测试派生健康状态枚举值."""
    assert tuple(
        status.value
        for status in RuntimeHealthStatus
    ) == (
        "healthy",
        "unhealthy",
        "unknown",
    )


def test_active_runtime_statuses() -> None:
    """测试当前实例只包含加载中和已加载状态."""
    assert ACTIVE_RUNTIME_STATUSES == (
        RuntimeStatus.STARTING.value,
        RuntimeStatus.RUNNING.value,
        RuntimeStatus.STOPPING.value,
    )
