# datamind/config/console.py

"""管理控制台配置

定义管理控制台的网络监听参数。

核心功能：
  - ConsoleConfig: 读取并校验管理控制台配置

属性：
  - host: 管理控制台监听地址
  - port: 管理控制台监听端口

环境变量：
  - DATAMIND_CONSOLE_HOST: 监听地址，默认 127.0.0.1
  - DATAMIND_CONSOLE_PORT: 监听端口，默认 8701

使用示例：
  from datamind.config.console import ConsoleConfig

  config = ConsoleConfig()

  print(config.host)
  print(config.port)
"""

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class ConsoleConfig(BaseSettings):
    """管理控制台配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_CONSOLE_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    host: str = "127.0.0.1"
    port: int = 8701

    @model_validator(mode="after")
    def validate_config(self) -> "ConsoleConfig":
        """校验管理控制台配置参数"""
        if not self.host.strip():
            raise ValueError(
                "host 不能为空"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError(
                "port 必须在 1 到 65535 之间，"
                f"当前值：{self.port}"
            )

        return self
