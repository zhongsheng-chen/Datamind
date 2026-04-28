"""审计装饰器

提供函数级别审计能力，自动记录操作行为并注入上下文信息。

核心功能：
  - audit: 审计装饰器，仅支持异步函数

使用示例：
  from datamind.audit.decorator import audit

  @audit(
      action="model.register",
      target_type="model",
      target_id_from="model_id",
  )
  async def register(model_id: str, name: str):
      ...
"""

from functools import wraps
from inspect import signature, iscoroutinefunction
from typing import Optional, Callable

from datamind.db.core import session_scope
from datamind.db.writer import AuditWriter
from datamind.audit.recorder import AuditRecorder


def audit(
    *,
    action: str,
    target_type: str,
    target_id_from: Optional[str] = None,
    target_id_func: Optional[Callable] = None,
):
    """审计装饰器

    参数：
        action: 操作类型（resource.operation）
        target_type: 目标类型
        target_id_from: 从函数参数中提取 target_id
        target_id_func: 自定义 target_id 生成函数
    """
    def decorator(func):
        sig = signature(func)

        if not iscoroutinefunction(func):
            raise TypeError(f"装饰器仅支持 async 函数：{func.__name__}")

        @wraps(func)
        async def wrapper(*args, **kwargs):
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            params = {
                k: v for k, v in bound.arguments.items()
                if k != "self"
            }

            if target_id_func:
                target_id = target_id_func(params)
            elif target_id_from:
                target_id = params.get(target_id_from)
            else:
                target_id = None

            writer = None
            recorder = None

            async with session_scope() as session:
                writer = AuditWriter(session)
                recorder = AuditRecorder(writer)

                try:
                    result = await func(*args, **kwargs)

                    await recorder.record(
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        status="success",
                        after={"result": result},
                        context={"params": params},
                    )

                    return result

                except Exception as e:
                    await recorder.record(
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        status="failed",
                        after={"error": str(e)},
                        context={"params": params},
                    )
                    raise

        return wrapper

    return decorator