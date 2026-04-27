# datamind/logging/logger.py

"""日志API

提供统一的日志获取接口，自动绑定当前上下文。

核心功能：
  - get_logger: 获取日志实例，自动绑定 trace_id、request_id 等上下文

使用示例：
  from datamind.logging import get_logger

  logger = get_logger(__name__)
  logger.info("用户登录成功", user_id=123, action="login")
"""

import structlog
from typing import Optional

from datamind.context.core import get_context


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """获取日志实例

    自动绑定当前上下文（trace_id、request_id、user、ip 等）。

    参数：
        name: 日志名称（可选）

    返回：
        structlog.BoundLogger 实例

    使用示例：
        from datamind.logging import get_logger

        logger = get_logger(__name__)
        logger.info("用户登录成功", user_id=123, action="login")
    """
    logger = structlog.get_logger(name)
    return logger.bind(**get_context())