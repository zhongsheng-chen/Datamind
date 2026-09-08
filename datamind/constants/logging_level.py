"""日志级别枚举

定义日志输出级别，用于日志过滤和审计。

核心功能：
  - LogLevel: 日志级别字符串枚举
  - SUPPORTED_LOG_LEVELS: 支持的日志级别集合

使用示例：
  from datamind.constants.logging_level import LogLevel

  if level == LogLevel.DEBUG:
      enable_debug_logging()
  elif level == LogLevel.CRITICAL:
      trigger_critical_alert()
"""

from enum import Enum
from typing import FrozenSet


class LogLevel(str, Enum):
    """日志级别字符串枚举"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_LOG_LEVELS: FrozenSet[str] = frozenset(
    str(log_level)
    for log_level in LogLevel
)
