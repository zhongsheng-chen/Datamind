"""运行实例在线状态测试

验证运行实例使用统一的心跳判定边界。

核心功能：
  - test_runtime_presence_detects_stale_active_instance:
    验证根据最近活动时间识别失联实例
  - test_runtime_presence_uses_heartbeat_grace_period:
    验证在线状态使用心跳宽限期
  - test_runtime_presence_returns_derived_health_status:
    验证返回推导后的健康状态
"""

from datetime import datetime, timedelta, timezone

from datamind.config import get_settings
from datamind.constants.runtime_status import RuntimeHealthStatus
from datamind.runtime.presence import (
    RuntimePresence,
)


CURRENT_TIME = datetime(
    2026,
    8,
    26,
    16,
    0,
    tzinfo=timezone.utc,
)


def test_runtime_presence_detects_stale_active_instance() -> None:
    """测试根据最近活动时间识别失联实例"""
    presence = RuntimePresence(
        stale_at=CURRENT_TIME,
    )

    assert presence.is_stale(
        status="running",
        activity_at=CURRENT_TIME - timedelta(seconds=1),
    ) is True
    assert presence.is_stale(
        status="running",
        activity_at=CURRENT_TIME,
    ) is False
    assert presence.is_stale(
        status="stopped",
        activity_at=None,
    ) is False


def test_runtime_presence_uses_heartbeat_grace_period() -> None:
    """测试按心跳间隔生成统一的失联判定时间"""
    presence = RuntimePresence.current(
        current_time=CURRENT_TIME,
    )
    grace_seconds = (
        get_settings().runtime.heartbeat_interval
        * 3
    )

    assert presence.stale_at == CURRENT_TIME - timedelta(
        seconds=grace_seconds
    )


def test_runtime_presence_returns_derived_health_status() -> None:
    """测试在线状态判定返回统一的健康状态枚举"""
    presence = RuntimePresence(
        stale_at=CURRENT_TIME,
    )

    assert presence.health_status(
        status="running",
        activity_at=CURRENT_TIME,
    ) is RuntimeHealthStatus.HEALTHY
    assert presence.health_status(
        status="running",
        activity_at=CURRENT_TIME - timedelta(seconds=1),
    ) is RuntimeHealthStatus.UNHEALTHY
    assert presence.health_status(
        status="stopped",
        activity_at=None,
    ) is RuntimeHealthStatus.UNKNOWN
