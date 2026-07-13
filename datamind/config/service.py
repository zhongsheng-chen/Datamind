# datamind/config/service.py

"""服务配置

定义服务运行参数、API 配置和运行时协调参数。

核心功能：
  - ServiceConfig: 读取并校验服务运行配置

属性：
  - name: 服务名称
  - version: 服务版本
  - environment: 运行环境，必填
  - host: 服务监听地址
  - port: 服务监听端口
  - workers: 工作进程数
  - timeout: 请求超时时间（秒）
  - reconcile_interval: 运行时状态协调间隔（秒）
  - heartbeat_interval: Worker 运行心跳间隔（秒）
  - enable_docs: 是否启用 API 文档
  - enable_health_check: 是否启用健康检查

环境变量：
  - DATAMIND_SERVICE_NAME: 服务名称，默认 datamind
  - DATAMIND_SERVICE_VERSION: 服务版本，默认 1.0.0
  - DATAMIND_SERVICE_ENVIRONMENT: 运行环境，必填
  - DATAMIND_SERVICE_HOST: 监听地址，默认 0.0.0.0
  - DATAMIND_SERVICE_PORT: 监听端口，默认 3000
  - DATAMIND_SERVICE_WORKERS: 工作进程数，默认 4
  - DATAMIND_SERVICE_TIMEOUT: 请求超时时间，默认 30
  - DATAMIND_SERVICE_RECONCILE_INTERVAL: 状态协调间隔，默认 2.0
  - DATAMIND_SERVICE_HEARTBEAT_INTERVAL: 运行心跳间隔，默认 30.0
  - DATAMIND_SERVICE_ENABLE_DOCS: 是否启用文档，默认 true
  - DATAMIND_SERVICE_ENABLE_HEALTH_CHECK: 是否启用健康检查，默认 true

使用示例：
  from datamind.config.service import ServiceConfig

  config = ServiceConfig()

  print(config.environment)
  print(config.port)
"""

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from datamind.constants import Environment


class ServiceConfig(BaseSettings):
    """服务配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_SERVICE_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    name: str = "datamind"
    version: str = "1.0.0"
    environment: Environment

    host: str = "0.0.0.0"
    port: int = 3000
    workers: int = 4
    timeout: int = 30

    reconcile_interval: float = 2.0
    heartbeat_interval: float = 30.0

    enable_docs: bool = True
    enable_health_check: bool = True

    @model_validator(mode="after")
    def validate_config(self) -> "ServiceConfig":
        """校验服务配置参数"""
        if not self.name.strip():
            raise ValueError(
                "name 不能为空"
            )

        if not self.version.strip():
            raise ValueError(
                "version 不能为空"
            )

        if not self.host.strip():
            raise ValueError(
                "host 不能为空"
            )

        if self.workers < 1:
            raise ValueError(
                "workers 必须大于等于 1，"
                f"当前值：{self.workers}"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError(
                "port 必须在 1 到 65535 之间，"
                f"当前值：{self.port}"
            )

        if self.timeout < 1:
            raise ValueError(
                "timeout 必须大于等于 1，"
                f"当前值：{self.timeout}"
            )

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

        return self
