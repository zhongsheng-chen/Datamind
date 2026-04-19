# datamind/constants/logging_format.py

"""日志格式常量

定义日志输出格式类型，用于结构化日志和文本日志。

核心功能：
  - LogFormat: 日志格式常量类
  - SUPPORTED_LOG_FORMATS: 支持的日志格式集合

使用示例：
  from datamind.constants.logging_format import LogFormat, SUPPORTED_LOG_FORMATS

  if format == LogFormat.json:
      enable_json_logging()
"""


class LogFormat:
    """日志格式常量"""

    TEXT: str = "text"
    JSON: str = "json"


SUPPORTED_LOG_FORMATS = frozenset({
    LogFormat.TEXT,
    LogFormat.JSON,
})