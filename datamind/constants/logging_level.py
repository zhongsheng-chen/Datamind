# datamind/constants/logging_level.py

"""日志级别常量

定义日志输出级别，用于日志过滤和审计。

核心功能：
  - LogLevel: 日志级别常量类
  - SUPPORTED_LOG_LEVELS: 支持的日志级别集合

使用示例：
  from datamind.constants.logging_level import LogLevel, SUPPORTED_LOG_LEVELS

  if level == LogLevel.DEBUG:
      enable_debug_logging()
"""


class LogLevel:
    """日志级别常量"""

    DEBUG: str = "DEBUG"
    INFO: str = "INFO"
    WARNING: str = "WARNING"
    ERROR: str = "ERROR"


SUPPORTED_LOG_LEVELS = frozenset({
    LogLevel.DEBUG,
    LogLevel.INFO,
    LogLevel.WARNING,
    LogLevel.ERROR,
})