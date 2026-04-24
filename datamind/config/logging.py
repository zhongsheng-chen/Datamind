# datamind/config/logging.py

"""日志配置

定义日志系统的配置参数，支持生产级别的日志管理。

属性：
  - level: 日志级别
  - format: 日志格式（json 或 text）
  - encoding: 日志编码
  - dir: 日志文件目录
  - filename: 日志文件名
  - date_format: 日期格式（None 表示 ISO 格式）
  - timezone: 时区
  - rotation: 轮转策略
  - rotation_when: 轮转时间间隔
  - rotation_interval: 轮转间隔数
  - max_bytes: 轮转大小阈值
  - backup_count: 备份文件数量
  - retention_days: 日志保留天数
  - enable_console: 是否输出到控制台
  - enable_file: 是否输出到文件
  - enable_async: 是否启用异步日志
  - sample_rate: 采样率
  - mask_sensitive: 是否脱敏敏感信息
  - mask_char: 脱敏字符
  - unmasked_prefix: 脱敏时前面保留位数
  - unmasked_suffix: 脱敏时后面保留位数

环境变量：
  - DATAMIND_LOG_LEVEL: 日志级别，默认 INFO
  - DATAMIND_LOG_FORMAT: 日志格式，默认 json
  - DATAMIND_LOG_ENCODING: 日志编码，默认 utf-8
  - DATAMIND_LOG_DIR: 日志目录，默认 logs
  - DATAMIND_LOG_FILENAME: 日志文件名，默认 datamind.log
  - DATAMIND_LOG_DATE_FORMAT: 日期格式，默认 None（ISO 格式）
  - DATAMIND_LOG_TIMEZONE: 时区，默认 Asia/Shanghai
  - DATAMIND_LOG_ROTATION: 轮转策略，默认 time
  - DATAMIND_LOG_ROTATION_WHEN: 轮转时间，默认 MIDNIGHT
  - DATAMIND_LOG_ROTATION_INTERVAL: 轮转间隔，默认 1
  - DATAMIND_LOG_MAX_BYTES: 轮转大小阈值，默认 104857600
  - DATAMIND_LOG_BACKUP_COUNT: 备份数量，默认 30
  - DATAMIND_LOG_RETENTION_DAYS: 保留天数，默认 90
  - DATAMIND_LOG_CONSOLE: 是否输出到控制台，默认 true
  - DATAMIND_LOG_FILE: 是否输出到文件，默认 true
  - DATAMIND_LOG_ENABLE_ASYNC: 是否启用异步日志，默认 false
  - DATAMIND_LOG_SAMPLE_RATE: 采样率，默认 1.0
  - DATAMIND_LOG_MASK_SENSITIVE: 是否脱敏，默认 true
  - DATAMIND_LOG_MASK_CHAR: 脱敏字符，默认 *
  - DATAMIND_LOG_UNMASKED_PREFIX: 脱敏前面保留位数，默认 2
  - DATAMIND_LOG_UNMASKED_SUFFIX: 脱敏后面保留位数，默认 2
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from pathlib import Path
from typing import Optional

from datamind.constants import (
    LogLevel, SUPPORTED_LOG_LEVELS,
    LogFormat, SUPPORTED_LOG_FORMATS,
    RotationType, SUPPORTED_ROTATION_TYPES,
    RotationWhen, SUPPORTED_ROTATION_WHEN,
    MB,
)


class LoggingConfig(BaseSettings):
    """日志配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_LOG_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    # 基础配置
    level: str = LogLevel.INFO
    format: str = LogFormat.JSON
    encoding: str = "utf-8"

    # 文件配置
    dir: Path = Path("logs")
    filename: str = "datamind.log"

    # 时间配置
    date_format: Optional[str] = None
    timezone: str = "Asia/Shanghai"

    # 轮转配置
    rotation: str = RotationType.TIME
    rotation_when: str = RotationWhen.MIDNIGHT
    rotation_interval: int = 1
    max_bytes: int = 100 * MB
    backup_count: int = 30
    retention_days: int = 90

    # 输出控制
    enable_console: bool = True
    enable_file: bool = True
    enable_async: bool = False

    # 性能控制
    sample_rate: float = 1.0

    # 安全配置
    mask_sensitive: bool = True
    mask_char: str = "*"
    unmasked_prefix: int = 2
    unmasked_suffix: int = 2

    @model_validator(mode="after")
    def validate(self):
        """校验配置参数"""
        if self.level not in SUPPORTED_LOG_LEVELS:
            raise ValueError(f"level 必须是 {SUPPORTED_LOG_LEVELS} 之一，当前值：{self.level}")

        if self.format not in SUPPORTED_LOG_FORMATS:
            raise ValueError(f"format 必须是 {SUPPORTED_LOG_FORMATS} 之一，当前值：{self.format}")

        if self.rotation not in SUPPORTED_ROTATION_TYPES:
            raise ValueError(f"rotation 必须是 {SUPPORTED_ROTATION_TYPES} 之一，当前值：{self.rotation}")

        if self.rotation_when not in SUPPORTED_ROTATION_WHEN:
            raise ValueError(f"rotation_when 必须是 {SUPPORTED_ROTATION_WHEN} 之一，当前值：{self.rotation_when}")

        if self.rotation_interval <= 0:
            raise ValueError(f"rotation_interval 必须大于 0，当前值：{self.rotation_interval}")

        if not 0 < self.sample_rate <= 1:
            raise ValueError(f"sample_rate 必须在 0 到 1 之间，当前值：{self.sample_rate}")

        if self.retention_days <= 0:
            raise ValueError(f"retention_days 必须大于 0，当前值：{self.retention_days}")

        if self.backup_count <= 0:
            raise ValueError(f"backup_count 必须大于 0，当前值：{self.backup_count}")

        if self.max_bytes <= 0:
            raise ValueError(f"max_bytes 必须大于 0，当前值：{self.max_bytes}")

        if self.unmasked_prefix < 0:
            raise ValueError(f"unmasked_prefix 必须大于等于 0，当前值：{self.unmasked_prefix}")

        if self.unmasked_suffix < 0:
            raise ValueError(f"unmasked_suffix 必须大于等于 0，当前值：{self.unmasked_suffix}")

        return self