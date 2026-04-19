# datamind/logging/logger.py

"""日志API

提供统一的日志获取接口。
"""

import structlog
from typing import Optional


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """获取日志实例

    参数：
        name: 日志名称（可选）

    返回：
        structlog.BoundLogger 实例

    使用示例：
        from datamind.logging import get_logger

        logger = get_logger(__name__)
        logger.info("用户登录成功", user_id=123, action="login")
    """
    return structlog.get_logger(name)