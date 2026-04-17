# datamind/config/logging.py

"""日志配置

定义日志输出级别和格式，满足金融审计要求。

属性：
  - level: 日志级别，DEBUG/INFO/WARNING/ERROR
  - format: 日志格式，text（文本）或 json（结构化JSON）

环境变量：
  - DATAMIND_LOGGING_LEVEL: 日志级别，默认 INFO
  - DATAMIND_LOGGING_FORMAT: 日志格式，默认 text
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class LoggingConfig(BaseSettings):
    """日志配置类"""

    level: str = "INFO"
    format: str = "text"

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_LOGGING_",
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate(self):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if self.level.upper() not in valid_levels:
            raise ValueError(f"level 必须是 {valid_levels} 之一，当前值：{self.level}")

        valid_formats = ["text", "json"]
        if self.format.lower() not in valid_formats:
            raise ValueError(f"format 必须是 {valid_formats} 之一，当前值：{self.format}")

        return self