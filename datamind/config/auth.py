"""认证配置

定义本地认证、JWT 和应急账户参数。

核心功能：
  - LocalAuthConfig: 读取并校验本地认证配置
  - AuthConfig: 读取并校验认证服务配置

环境变量：
  - DATAMIND_AUTH_ENABLED: 是否启用认证功能，默认 false
  - DATAMIND_AUTH_SECRET_KEY: JWT 签名密钥，默认空
  - DATAMIND_AUTH_ALGORITHM: JWT 签名算法，默认 HS256
  - DATAMIND_AUTH_ACCESS_TOKEN_EXPIRES_MINUTES:
    访问令牌有效时间，默认 30
  - DATAMIND_AUTH_REFRESH_TOKEN_EXPIRES_DAYS:
    刷新令牌有效时间，默认 7
  - DATAMIND_AUTH_LOCAL_MAX_FAILED_LOGIN_ATTEMPTS:
    最大连续登录失败次数，默认 5
  - DATAMIND_AUTH_LOCAL_LOCK_MINUTES:
    登录失败锁定时间，默认 30
  - DATAMIND_AUTH_LOCAL_UPGRADE_PASSWORD_HASH:
    是否自动升级密码哈希，默认 true
  - DATAMIND_AUTH_LOCAL_BREAK_GLASS_ONLY:
    是否仅允许应急账户登录，默认 false
  - DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS:
    本地认证允许访问的网段，默认 []
  - DATAMIND_AUTH_LOCAL_BREAK_GLASS_ACCESS_TOKEN_EXPIRES_MINUTES:
    应急访问令牌有效时间，默认 15

使用示例：
  from datamind.config.auth import AuthConfig

  config = AuthConfig()

  print(config.enabled)
  print(config.local.allowed_networks)
"""

from ipaddress import ip_network

from pydantic import (
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class LocalAuthConfig(BaseSettings):
    """本地认证配置"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_AUTH_LOCAL_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    max_failed_login_attempts: int = 5
    lock_minutes: int = 30
    upgrade_password_hash: bool = True
    break_glass_only: bool = False
    allowed_networks: tuple[str, ...] = ()
    break_glass_access_token_expires_minutes: int = 15

    @model_validator(mode="after")
    def validate_config(self) -> "LocalAuthConfig":
        """校验本地认证配置参数"""
        if self.max_failed_login_attempts <= 0:
            raise ValueError(
                "max_failed_login_attempts 必须大于 0，"
                f"当前值：{self.max_failed_login_attempts}"
            )

        if self.lock_minutes <= 0:
            raise ValueError(
                "lock_minutes 必须大于 0，"
                f"当前值：{self.lock_minutes}"
            )

        if self.break_glass_access_token_expires_minutes <= 0:
            raise ValueError(
                "break_glass_access_token_expires_minutes "
                "必须大于 0，"
                "当前值："
                f"{self.break_glass_access_token_expires_minutes}"
            )

        for network in self.allowed_networks:
            try:
                ip_network(
                    network,
                    strict=False,
                )
            except ValueError as exc:
                raise ValueError(
                    "allowed_networks 包含无效网段: "
                    f"{network}"
                ) from exc

        return self


class AuthConfig(BaseSettings):
    """认证配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_AUTH_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    enabled: bool = False
    secret_key: SecretStr = SecretStr("")
    algorithm: str = "HS256"
    access_token_expires_minutes: int = 30
    refresh_token_expires_days: int = 7
    local: LocalAuthConfig = Field(
        default_factory=LocalAuthConfig
    )

    @model_validator(mode="after")
    def validate_config(self) -> "AuthConfig":
        """校验认证配置参数"""
        if not self.algorithm.strip():
            raise ValueError(
                "algorithm 不能为空"
            )

        if self.access_token_expires_minutes <= 0:
            raise ValueError(
                "access_token_expires_minutes 必须大于 0，"
                f"当前值：{self.access_token_expires_minutes}"
            )

        if self.refresh_token_expires_days <= 0:
            raise ValueError(
                "refresh_token_expires_days 必须大于 0，"
                f"当前值：{self.refresh_token_expires_days}"
            )

        if (
                self.enabled
                and not self.secret_key.get_secret_value()
        ):
            raise ValueError(
                "启用认证功能时，secret_key 不能为空"
            )

        return self


__all__ = [
    "LocalAuthConfig",
    "AuthConfig",
]
