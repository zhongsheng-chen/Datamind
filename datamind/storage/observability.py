# datamind/storage/observability.py

"""存储可观测性装饰器

提供存储操作的统一可观测性能力，包括性能监控和错误追踪。

核心功能：
  - observe_storage: 装饰器，监控存储操作的执行时间、成功率和错误

使用示例：
  from datamind.storage.observability import observe_storage

  class LocalStorageBackend(BaseStorageBackend):
      @observe_storage("put")
      def put(self, key: str, data: bytes) -> None:
          ...
"""

import time
import structlog
import functools

from datamind.context import get_context


logger = structlog.get_logger(__name__)

def observe_storage(op: str):
    """存储操作可观测性装饰器

    参数：
        op: 操作名称，如 put / get / delete / list

    使用示例：
        @observe_storage("put")
        def put(self, key, data):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            ctx = get_context()
            start = time.time()

            try:
                result = func(self, *args, **kwargs)

                logger.info(
                    "存储操作成功",
                    operation=op,
                    status="success",
                    latency_ms=round((time.time() - start) * 1000, 2),
                    storage_type=getattr(self.config, "type", None)
                    if hasattr(self, "config") else None,
                    **ctx
                )

                return result

            except Exception as e:
                logger.exception(
                    "存储操作失败",
                    operation=op,
                    status="error",
                    error_type=type(e).__name__,
                    storage_type=getattr(self.config, "type", None)
                    if hasattr(self, "config") else None,
                    **ctx
                )
                raise

        return wrapper
    return decorator