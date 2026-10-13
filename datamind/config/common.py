"""应用通用配置.

定义各组件共用的运行环境和默认时区。

核心功能：
  - CommonConfig: 读取并校验应用通用配置

属性：
  - environment: 运行环境，必填
  - timezone: IANA 时区名称

环境变量：
  - DATAMIND_ENVIRONMENT:
    运行环境，必填
  - DATAMIND_TIMEZONE:
    默认时区，默认 Asia/Shanghai

使用示例：
  from datamind.config.common import CommonConfig

  config = CommonConfig()

  print(config.environment)
  print(config.timezone)
"""

from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from pydantic import (
    Field,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from datamind.constants import Environment


class CommonConfig(BaseSettings):
    """应用通用配置类."""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    environment: Environment = Field(
        description="应用运行环境，供资源管理、流量分配和认证策略使用，必填。",
    )

    timezone: str = Field(
        default="Asia/Shanghai",
        description="应用默认时区，用于日志、命令行时间显示和未带时区的时间输入解析。",
    )

    @model_validator(mode="after")
    def validate_timezone(self) -> "CommonConfig":
        """校验默认时区配置."""
        if not self.timezone.strip():
            raise ValueError(
                "timezone 不能为空"
            )

        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"timezone 不是有效的 IANA 时区，当前值：{self.timezone}"
            ) from exc

        return self
