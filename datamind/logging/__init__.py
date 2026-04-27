# datamind/logging/__init__.py

"""日志模块

基于 structlog 的结构化日志系统，支持 JSON 和文本两种输出格式。

核心功能：
  - setup_logging: 初始化日志系统
  - get_logger: 获取日志实例，自动绑定上下文

使用示例：
  from datamind.logging import setup_logging, get_logger

  # 初始化日志系统
  setup_logging(settings.logging)

  # 获取日志实例（自动绑定 trace_id 等上下文）
  logger = get_logger(__name__)
  logger.info("用户登录成功", user_id=123, action="login")
"""

from datamind.logging.setup import setup_logging
from datamind.logging.logger import get_logger

__all__ = [
    "setup_logging",
    "get_logger",
]