"""日志 API

提供统一的日志获取接口。

日志上下文由处理器在每次写入日志时动态补充，
避免重复绑定或使用过期上下文。

核心功能：
  - get_logger: 获取指定名称的日志实例

使用示例：
  from datamind.logging import get_logger

  logger = get_logger(__name__)
  logger.info(
      "用户登录成功",
      user="admin",
      action="login",
  )
"""

import structlog


def get_logger(
        name: str | None = None,
) -> structlog.stdlib.BoundLogger:
    """获取日志实例

    参数：
        name: 日志名称，通常传入 __name__

    返回：
        structlog.stdlib.BoundLogger 实例
    """
    return structlog.get_logger(
        name
    )
