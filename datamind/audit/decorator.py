# datamind/audit/decorator.py

"""审计装饰器

提供函数级别审计能力，自动记录操作行为并注入上下文信息。

核心功能：
  - audit: 审计装饰器，仅支持异步函数，自动记录成功和失败事件。

使用示例：
  from datamind.audit import audit

  @audit(
      action="model.register",
      target_type="model",
      target_id_from="model_id",
  )
  async def register_model(model_id: str, name: str):
      ...
"""

from functools import wraps
from inspect import signature, iscoroutinefunction
from typing import Optional, Callable

from datamind.audit.recorder import AuditRecorder
from datamind.audit.errors import AuditValidationError


def audit(
    *,
    action: str,
    target_type: str,
    target_id_from: Optional[str] = None,
    target_id_func: Optional[Callable] = None,
    before_func: Optional[Callable[[dict], dict]] = None,
    after_func: Optional[Callable[[dict, object], dict]] = None,
):
    """审计装饰器

    参数：
        action: 操作类型，格式为 resource.operation
        target_type: 目标类型
        target_id_from: 从函数参数中提取 target_id 的参数名
        target_id_func: 自定义 target_id 生成函数，接收参数字典和返回值
        before_func: 自定义 before 提取函数，接收参数字典返回变更前数据
        after_func: 自定义 after 提取函数，接收参数字典和函数返回值，返回变更后数据

    异常：
        TypeError: 装饰的函数不是异步函数
    """
    def decorator(func):
        sig = signature(func)

        if not iscoroutinefunction(func):
            raise TypeError(
                f"装饰器仅支持 async 函数：{func.__name__}"
            )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            params = {
                k: v for k, v in bound.arguments.items()
                if k != "self"
            }

            before = (
                before_func(params)
                if before_func else None
            )

            recorder = AuditRecorder()

            # 优先从参数中解析
            if target_id_from:
                target_id = params.get(
                    target_id_from
                )
            else:
                target_id = None

            try:
                result = await func(
                    *args,
                    **kwargs,
                )

                # 如果参数中没有，再从返回值动态解析
                if (
                    not target_id
                    and target_id_func
                ):
                    target_id = target_id_func(
                        params,
                        result,
                    )

                if not target_id:
                    raise AuditValidationError(
                        f"缺少 target_id，无法从参数中解析目标ID（参数：{', '.join(params.keys())}）"
                    )

                if after_func:
                    after = after_func(
                        params,
                        result,
                    )
                else:
                    after = result

                await recorder.record(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    status="success",
                    error=None,
                    before=before,
                    after=after,
                    context={
                        "params": params
                    },
                )

                return result

            except Exception as e:
                await recorder.record(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    status="failed",
                    error=str(e),
                    before=before,
                    after=None,
                    context={
                        "params": params
                    },
                )

                raise

        return wrapper

    return decorator