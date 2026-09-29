"""日志配置.

定义日志级别、输出格式、文件轮转、保留策略、采样和脱敏参数。

核心功能：
  - LoggingConfig: 读取并校验日志系统配置

属性：
  - level: 日志级别
  - format: 日志格式
  - encoding: 日志编码
  - dir: 日志文件目录
  - filename: 日志文件名
  - date_format: 日期格式
  - timezone: IANA 时区名称
  - rotation: 日志轮转策略
  - rotation_when: 时间轮转周期
  - rotation_interval: 日志轮转间隔
  - max_bytes: 大小轮转阈值
  - backup_count: 轮转备份文件数量
  - retention_days: 日志保留天数
  - enable_console: 是否输出到控制台
  - console_level: 控制台日志级别
  - enable_file: 是否输出到文件
  - enable_async: 是否启用异步日志
  - sample_rate: 普通日志采样率
  - mask_sensitive: 是否脱敏敏感信息
  - mask_char: 脱敏字符
  - unmasked_prefix: 脱敏时前面保留位数
  - unmasked_suffix: 脱敏时后面保留位数

环境变量：
  - DATAMIND_LOG_LEVEL:
    日志级别，默认 INFO
  - DATAMIND_LOG_FORMAT:
    日志格式，默认 json
  - DATAMIND_LOG_ENCODING:
    日志编码，默认 utf-8
  - DATAMIND_LOG_DIR:
    日志目录，默认 logs
  - DATAMIND_LOG_FILENAME:
    日志文件名，默认 datamind.log
  - DATAMIND_LOG_DATE_FORMAT:
    日期格式，默认 None
  - DATAMIND_LOG_TIMEZONE:
    时区，默认 Asia/Shanghai
  - DATAMIND_LOG_ROTATION:
    轮转策略，默认 time
  - DATAMIND_LOG_ROTATION_WHEN:
    轮转周期，默认 MIDNIGHT
  - DATAMIND_LOG_ROTATION_INTERVAL:
    轮转间隔，默认 1
  - DATAMIND_LOG_MAX_BYTES:
    大小轮转阈值，默认 104857600
  - DATAMIND_LOG_BACKUP_COUNT:
    备份数量，默认 30
  - DATAMIND_LOG_RETENTION_DAYS:
    保留天数，默认 90
  - DATAMIND_LOG_ENABLE_CONSOLE:
    是否输出到控制台，默认 true
  - DATAMIND_LOG_CONSOLE_LEVEL:
    控制台日志级别，默认 WARNING
  - DATAMIND_LOG_ENABLE_FILE:
    是否输出到文件，默认 true
  - DATAMIND_LOG_ENABLE_ASYNC:
    是否启用异步日志，默认 false
  - DATAMIND_LOG_SAMPLE_RATE:
    普通日志采样率，默认 1.0
  - DATAMIND_LOG_MASK_SENSITIVE:
    是否脱敏，默认 true
  - DATAMIND_LOG_MASK_CHAR:
    脱敏字符，默认 *
  - DATAMIND_LOG_UNMASKED_PREFIX:
    脱敏前面保留位数，默认 2
  - DATAMIND_LOG_UNMASKED_SUFFIX:
    脱敏后面保留位数，默认 2

使用示例：
  from datamind.config.logging import LoggingConfig

  config = LoggingConfig()

  print(config.level)
  print(config.format)
  print(config.dir)
"""

import codecs
from pathlib import Path
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from datamind.constants import (
    LogFormat,
    LogLevel,
    MB,
    RotationType,
    RotationWhen,
)


class LoggingConfig(BaseSettings):
    """日志配置类."""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_LOG_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    encoding: str = "utf-8"

    dir: Path = Path("logs")
    filename: str = "datamind.log"

    date_format: str | None = None
    timezone: str = "Asia/Shanghai"

    rotation: RotationType = RotationType.TIME
    rotation_when: RotationWhen = RotationWhen.MIDNIGHT
    rotation_interval: int = 1
    max_bytes: int = 100 * MB
    backup_count: int = 30
    retention_days: int = 90

    enable_console: bool = True
    console_level: LogLevel = LogLevel.WARNING
    enable_file: bool = True
    enable_async: bool = False

    sample_rate: float = 1.0

    mask_sensitive: bool = True
    mask_char: str = "*"
    unmasked_prefix: int = 2
    unmasked_suffix: int = 2

    @model_validator(mode="after")
    def validate_config(self) -> "LoggingConfig":
        """校验日志配置参数."""
        if not self.encoding.strip():
            raise ValueError(
                "encoding 不能为空"
            )

        try:
            codecs.lookup(self.encoding)
        except LookupError as exc:
            raise ValueError(
                "encoding 不是有效的字符编码，"
                f"当前值：{self.encoding}"
            ) from exc

        if not self.filename.strip():
            raise ValueError(
                "filename 不能为空"
            )

        if (
            self.date_format is not None
            and not self.date_format.strip()
        ):
            raise ValueError(
                "date_format 不能是空字符串"
            )

        if not self.timezone.strip():
            raise ValueError(
                "timezone 不能为空"
            )

        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                "timezone 不是有效的 IANA 时区，"
                f"当前值：{self.timezone}"
            ) from exc

        if self.rotation_interval <= 0:
            raise ValueError(
                "rotation_interval 必须大于 0，"
                f"当前值：{self.rotation_interval}"
            )

        if self.max_bytes <= 0:
            raise ValueError(
                "max_bytes 必须大于 0，"
                f"当前值：{self.max_bytes}"
            )

        if self.backup_count <= 0:
            raise ValueError(
                "backup_count 必须大于 0，"
                f"当前值：{self.backup_count}"
            )

        if self.retention_days <= 0:
            raise ValueError(
                "retention_days 必须大于 0，"
                f"当前值：{self.retention_days}"
            )

        if not 0 < self.sample_rate <= 1:
            raise ValueError(
                "sample_rate 必须大于 0 "
                "且小于等于 1，"
                f"当前值：{self.sample_rate}"
            )

        if not self.mask_char:
            raise ValueError(
                "mask_char 不能为空"
            )

        if len(self.mask_char) != 1:
            raise ValueError(
                "mask_char 只能包含一个字符，"
                f"当前值：{self.mask_char}"
            )

        if self.unmasked_prefix < 0:
            raise ValueError(
                "unmasked_prefix 必须大于等于 0，"
                f"当前值：{self.unmasked_prefix}"
            )

        if self.unmasked_suffix < 0:
            raise ValueError(
                "unmasked_suffix 必须大于等于 0，"
                f"当前值：{self.unmasked_suffix}"
            )

        return self
