"""审计配置

定义审计服务的启用状态、失败策略和数据库重试参数。

核心功能：
  - AuditConfig: 读取并校验审计组件配置

属性：
  - enabled: 是否启用审计组件
  - failure_mode: 审计失败处理模式
  - max_retries: 瞬时数据库错误最大尝试次数
  - retry_base_delay: 重试基础延迟（秒）

环境变量：
  - DATAMIND_AUDIT_ENABLED: 是否启用审计组件，默认 true
  - DATAMIND_AUDIT_FAILURE_MODE: 失败处理模式，默认 open
  - DATAMIND_AUDIT_MAX_RETRIES: 最大尝试次数，默认 2
  - DATAMIND_AUDIT_RETRY_BASE_DELAY: 重试基础延迟，默认 0.05
"""

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from datamind.audit.policy import AuditFailureMode


class AuditConfig(BaseSettings):
    """审计配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_AUDIT_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    enabled: bool = True
    failure_mode: AuditFailureMode = AuditFailureMode.OPEN
    max_retries: int = 2
    retry_base_delay: float = 0.05

    @model_validator(mode="after")
    def validate_config(self) -> "AuditConfig":
        """校验审计配置参数"""
        if self.max_retries < 1:
            raise ValueError(
                "max_retries 必须大于等于 1，"
                f"当前值：{self.max_retries}"
            )

        if self.retry_base_delay <= 0:
            raise ValueError(
                "retry_base_delay 必须大于 0，"
                f"当前值：{self.retry_base_delay}"
            )

        return self
