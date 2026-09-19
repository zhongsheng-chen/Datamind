"""系统初始化配置

定义首次初始化使用的管理员账户凭据。

核心功能：
  - InitializationConfig: 读取系统初始化配置

环境变量：
  - DATAMIND_INIT_ADMIN_USERNAME:
    管理员用户名，默认 admin
  - DATAMIND_INIT_ADMIN_PASSWORD:
    管理员密码，默认 admin

使用示例：
  from datamind.config.initialization import InitializationConfig

  config = InitializationConfig()

  print(config.admin_username)
"""

from pydantic import (
    SecretStr,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class InitializationConfig(BaseSettings):
    """系统初始化配置"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_INIT_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    admin_username: str = "admin"
    admin_password: SecretStr = SecretStr("admin")

    @field_validator("admin_username")
    @classmethod
    def validate_admin_username(
            cls,
            value: str,
    ) -> str:
        """校验并规范化管理员用户名"""
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "admin_username 不能为空"
            )

        if len(normalized) > 64:
            raise ValueError(
                "admin_username 长度不能超过 64"
            )

        return normalized


__all__ = [
    "InitializationConfig",
]
