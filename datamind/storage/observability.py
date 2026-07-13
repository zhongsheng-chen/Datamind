# datamind/storage/observability.py

"""存储可观测性装饰器

提供存储操作的统一可观测性能力，包括性能监控和错误追踪。

核心功能：
  - observe_storage: 装饰器，监控存储操作的执行时间、成功状态和异常信息

使用示例：
  from datamind.storage.observability import observe_storage

  class StorageAdmin:
      @property
      def storage_type(
              self,
      ) -> str:
          return self.backend.__class__.__name__

      @observe_storage("save")
      def save(
              self,
              key: str,
              data: bytes,
      ) -> str:
          ...
"""

import functools
import time
from collections.abc import Callable, Mapping
from typing import Any, ParamSpec, TypeVar

import structlog

from datamind.context import get_context

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def _get_latency_ms(
        started_at: float,
) -> float:
    """计算操作耗时

    参数：
        started_at: 操作开始时间

    返回：
        毫秒级耗时，保留两位小数
    """
    return round(
        (
                time.perf_counter()
                - started_at
        ) * 1000,
        2,
    )


def _build_event_fields(
        *,
        context: Mapping[str, Any],
        operation: str,
        status: str,
        latency_ms: float,
        storage_type: str,
        error: Exception | None = None,
) -> dict[str, Any]:
    """构造存储操作日志字段

    参数：
        context: 当前上下文
        operation: 操作名称
        status: 操作状态
        latency_ms: 操作耗时
        storage_type: 存储后端类型
        error: 操作异常

    返回：
        结构化日志字段
    """
    event_fields: dict[str, Any] = {
        **context,
        "operation": operation,
        "status": status,
        "latency_ms": latency_ms,
        "storage_type": storage_type,
    }

    if error is not None:
        event_fields.update(
            {
                "error_type": error.__class__.__name__,
                "error": str(error),
            }
        )

    return event_fields


def _get_storage_type(
        target: object,
) -> str:
    """获取被装饰对象的存储类型

    参数：
        target: 被装饰方法所属对象

    返回：
        存储后端类型

    异常：
        TypeError: 对象未提供有效的 storage_type 属性
    """
    storage_type = getattr(
        target,
        "storage_type",
        None,
    )

    if not isinstance(
            storage_type,
            str,
    ):
        raise TypeError(
            "observe_storage 只能装饰提供 "
            "storage_type 属性的对象方法"
        )

    return storage_type


def observe_storage(
        operation: str,
) -> Callable[
    [Callable[P, R]],
    Callable[P, R],
]:
    """存储操作可观测性装饰器

    参数：
        operation: 操作名称，例如 save / load / delete / list

    返回：
        包装后的存储操作函数
    """

    def decorator(
            func: Callable[P, R],
    ) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(
                *args: P.args,
                **kwargs: P.kwargs,
        ) -> R:
            if not args:
                raise TypeError(
                    "observe_storage 只能装饰实例方法"
                )

            context = get_context()
            storage_type = _get_storage_type(
                args[0]
            )
            started_at = time.perf_counter()

            try:
                result = func(
                    *args,
                    **kwargs,
                )

            except Exception as exc:
                event_fields = _build_event_fields(
                    context=context,
                    operation=operation,
                    status="error",
                    latency_ms=_get_latency_ms(
                        started_at
                    ),
                    storage_type=storage_type,
                    error=exc,
                )

                logger.exception(
                    "存储操作失败",
                    **event_fields,
                )

                raise

            event_fields = _build_event_fields(
                context=context,
                operation=operation,
                status="success",
                latency_ms=_get_latency_ms(
                    started_at
                ),
                storage_type=storage_type,
            )

            logger.debug(
                "存储操作成功",
                **event_fields,
            )

            return result

        return wrapper

    return decorator
