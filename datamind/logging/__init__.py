"""日志模块.

基于 structlog 的结构化日志系统，
支持 JSON 和文本输出以及同步、异步日志。

日志上下文由处理器在每次写入日志时动态补充。

核心功能：
  - setup_logging: 初始化日志系统
  - shutdown_logging: 关闭日志系统并释放日志资源
  - get_logger: 获取日志实例

使用示例：
  from datamind.logging import (
      get_logger,
      setup_logging,
      shutdown_logging,
  )

  # 初始化日志系统
  setup_logging(
      settings.logging
  )

  # 获取日志实例
  logger = get_logger(__name__)
  logger.info(
      "用户登录成功",
      user_id=123,
      action="login",
  )

  # 进程退出前关闭日志系统
  shutdown_logging()
"""

from datamind.logging.logger import get_logger
from datamind.logging.setup import (
    setup_logging,
    shutdown_logging,
)


__all__ = [
    "setup_logging",
    "shutdown_logging",
    "get_logger",
]
