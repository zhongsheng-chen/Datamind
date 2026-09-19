"""服务配置

定义服务标识、网络、进程和 API 参数。

核心功能：
  - ServiceConfig: 读取并校验服务运行配置

属性：
  - name: 服务名称
  - version: 服务版本
  - environment: 运行环境，必填
  - host: 服务监听地址
  - port: 服务监听端口
  - workers: 工作进程数
  - timeout: 认证后单条或整批预测请求的超时时间（秒），不包含启动等待
  - enable_docs: 是否启用 API 文档
  - enable_health_check: 是否启用健康检查

环境变量：
  - DATAMIND_SERVICE_NAME:
    服务名称，默认 datamind
  - DATAMIND_SERVICE_VERSION:
    服务版本，默认 1.0.0
  - DATAMIND_SERVICE_ENVIRONMENT:
    运行环境，必填
  - DATAMIND_SERVICE_HOST:
    监听地址，默认 0.0.0.0
  - DATAMIND_SERVICE_PORT:
    监听端口，默认 8700
  - DATAMIND_SERVICE_WORKERS:
    工作进程数，默认 4
  - DATAMIND_SERVICE_TIMEOUT:
    预测请求超时时间，默认 30 秒
  - DATAMIND_SERVICE_ENABLE_DOCS:
    是否启用文档，默认 true
  - DATAMIND_SERVICE_ENABLE_HEALTH_CHECK:
    是否启用健康检查，默认 true

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
    port: int = 8700
    workers: int = 4
    timeout: int = 30

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

        return self
