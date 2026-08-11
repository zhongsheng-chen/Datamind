# datamind/config/runtime.py

"""运行时配置

定义状态协调、心跳与影子执行参数。

核心功能：
  - RuntimeConfig: 读取并校验运行时配置

属性：
  - reconcile_interval: 运行状态协调间隔（秒）
  - heartbeat_interval: Worker 运行心跳间隔（秒）
  - shadow_enabled: 是否执行影子预测
  - shadow_queue_size: 单个 Worker 的影子任务队列容量
  - shadow_worker_count: 单个 Worker 的影子执行并发数
  - shadow_timeout: 单次影子预测超时时间（秒）

环境变量：
  - DATAMIND_RUNTIME_RECONCILE_INTERVAL: 状态协调间隔，默认 2.0
  - DATAMIND_RUNTIME_HEARTBEAT_INTERVAL: 运行心跳间隔，默认 30.0
  - DATAMIND_RUNTIME_SHADOW_ENABLED: 是否执行影子预测，默认 true
  - DATAMIND_RUNTIME_SHADOW_QUEUE_SIZE: 影子任务队列容量，默认 1024
  - DATAMIND_RUNTIME_SHADOW_WORKER_COUNT: 影子执行并发数，默认 2
  - DATAMIND_RUNTIME_SHADOW_TIMEOUT: 影子预测超时时间，默认 5.0

使用示例：
  from datamind.config.runtime import RuntimeConfig

  config = RuntimeConfig()

  print(config.reconcile_interval)
  print(config.shadow_enabled)
"""

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class RuntimeConfig(BaseSettings):
    """运行时配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_RUNTIME_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    reconcile_interval: float = 2.0
    heartbeat_interval: float = 30.0

    shadow_enabled: bool = True
    shadow_queue_size: int = 1024
    shadow_worker_count: int = 2
    shadow_timeout: float = 5.0

    @model_validator(mode="after")
    def validate_config(self) -> "RuntimeConfig":
        """校验运行时配置参数"""
        if self.reconcile_interval <= 0:
            raise ValueError(
                "reconcile_interval 必须大于 0，"
                f"当前值：{self.reconcile_interval}"
            )

        if self.heartbeat_interval <= 0:
            raise ValueError(
                "heartbeat_interval 必须大于 0，"
                f"当前值：{self.heartbeat_interval}"
            )

        if self.shadow_queue_size < 1:
            raise ValueError(
                "shadow_queue_size 必须大于等于 1，"
                f"当前值：{self.shadow_queue_size}"
            )

        if self.shadow_worker_count < 1:
            raise ValueError(
                "shadow_worker_count 必须大于等于 1，"
                f"当前值：{self.shadow_worker_count}"
            )

        if self.shadow_timeout <= 0:
            raise ValueError(
                "shadow_timeout 必须大于 0，"
                f"当前值：{self.shadow_timeout}"
            )

        return self
