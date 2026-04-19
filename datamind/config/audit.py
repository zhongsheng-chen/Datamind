# datamind/config/audit.py

"""审计配置

定义审计日志的配置参数，满足金融监管要求。

属性：
  - enable_request_log: 是否记录请求日志
  - enable_response_log: 是否记录响应日志
  - log_request_body: 是否记录请求体
  - log_response_body: 是否记录响应体
  - trace_id_header: 链路追踪ID的HTTP头名称
  - retention_days: 日志保留天数

环境变量：
  - DATAMIND_AUDIT_ENABLE_REQUEST_LOG: 是否记录请求日志，默认 true
  - DATAMIND_AUDIT_ENABLE_RESPONSE_LOG: 是否记录响应日志，默认 true
  - DATAMIND_AUDIT_LOG_REQUEST_BODY: 是否记录请求体，默认 true
  - DATAMIND_AUDIT_LOG_RESPONSE_BODY: 是否记录响应体，默认 false
  - DATAMIND_AUDIT_TRACE_ID_HEADER: 追踪ID头，默认 X-Trace-Id
  - DATAMIND_AUDIT_RETENTION_DAYS: 保留天数，默认 365
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class AuditConfig(BaseSettings):
    """审计配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_AUDIT_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    enable_request_log: bool = True
    enable_response_log: bool = True
    log_request_body: bool = True
    log_response_body: bool = False
    trace_id_header: str = "X-Trace-Id"
    retention_days: int = 365

    @model_validator(mode="after")
    def validate(self):
        """校验配置参数"""
        if not self.trace_id_header:
            raise ValueError("trace_id_header 不能为空")

        if self.retention_days <= 0:
            raise ValueError(f"retention_days 必须大于 0，当前值：{self.retention_days}")

        return self