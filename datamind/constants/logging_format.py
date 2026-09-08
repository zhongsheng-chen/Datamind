"""日志格式枚举

定义日志输出格式类型，用于结构化日志和文本日志。

核心功能：
  - LogFormat: 日志格式字符串枚举
  - SUPPORTED_LOG_FORMATS: 支持的日志格式集合

使用示例：
  from datamind.constants.logging_format import LogFormat

  if log_format == LogFormat.JSON:
      enable_json_logging()
  elif log_format == LogFormat.TEXT:
      enable_text_logging()
"""

from enum import Enum
from typing import FrozenSet


class LogFormat(str, Enum):
    """日志格式字符串枚举"""

    TEXT = "text"
    JSON = "json"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_LOG_FORMATS: FrozenSet[str] = frozenset(
    str(log_format)
    for log_format in LogFormat
)
