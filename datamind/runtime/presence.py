"""运行实例在线状态.

统一定义运行实例的心跳有效期和失联判定。

核心功能：
  - RuntimePresence: 判断运行实例是否仍然在线
"""

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from datamind.config import get_runtime_config
from datamind.constants.runtime_status import (
    ACTIVE_RUNTIME_STATUSES,
    RuntimeHealthStatus,
)


_HEARTBEAT_GRACE_PERIODS = 3


@dataclass(frozen=True)
class RuntimePresence:
    """运行实例的在线状态判定."""

    stale_at: datetime

    @classmethod
    def current(
            cls,
            *,
            current_time: datetime | None = None,
    ) -> "RuntimePresence":
        """根据心跳配置创建当前在线状态判定."""
        heartbeat_interval = (
            get_runtime_config().heartbeat_interval
        )
        stale_at = (
            current_time
            or datetime.now(timezone.utc)
        ) - timedelta(
            seconds=(
                heartbeat_interval
                * _HEARTBEAT_GRACE_PERIODS
            )
        )

        return cls(
            stale_at=stale_at,
        )

    def is_stale(
            self,
            *,
            status: str,
            activity_at: datetime | None,
    ) -> bool:
        """判断运行实例是否已经失联."""
        if status not in ACTIVE_RUNTIME_STATUSES:
            return False

        if activity_at is None:
            return True

        if activity_at.tzinfo is None:
            activity_at = activity_at.replace(
                tzinfo=timezone.utc
            )

        return activity_at < self.stale_at

    def health_status(
            self,
            *,
            status: str,
            activity_at: datetime | None,
    ) -> RuntimeHealthStatus:
        """根据运行状态与最近活动时间计算健康状态."""
        if status not in ACTIVE_RUNTIME_STATUSES:
            return RuntimeHealthStatus.UNKNOWN

        if self.is_stale(
                status=status,
                activity_at=activity_at,
        ):
            return RuntimeHealthStatus.UNHEALTHY

        return RuntimeHealthStatus.HEALTHY
