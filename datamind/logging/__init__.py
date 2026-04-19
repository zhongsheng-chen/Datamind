# datamind/logging/__init__.py

"""日志模块

基于 structlog 的结构化日志系统，支持 JSON 和文本两种输出格式。

核心功能：
  - setup_logging: 初始化日志系统
  - get_logger: 获取日志实例
  - set_context: 设置上下文（trace_id / request_id）
  - get_context: 获取当前上下文
  - clear_context: 清除上下文
  - request_context: 请求级别上下文管理器

使用示例：
  from datamind.logging import setup_logging, get_logger, request_context

  # 初始化日志系统
  setup_logging(settings.logging)

  # 使用上下文管理器
  with request_context(trace_id="trace-123456", request_id="req-789"):
      logger = get_logger(__name__)
      logger.info("用户登录成功", user_id=123, action="login")
"""

from datamind.logging.context import (
    set_context,
    get_context,
    clear_context,
    request_context,
)
from datamind.logging.logger import get_logger
from datamind.logging.setup import setup_logging

__all__ = [
    "setup_logging",
    "get_logger",
    "set_context",
    "get_context",
    "clear_context",
    "request_context",
]