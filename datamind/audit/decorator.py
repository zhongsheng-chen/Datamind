# datamind/audit/decorator.py

"""审计装饰器

提供函数级别审计能力，自动记录操作行为并注入上下文信息。

核心功能：
  - audit: 审计装饰器，函数执行后自动记录审计日志

使用示例：

  from datamind.audit.decorator import audit


  # 模型注册
  @audit(
      action="model.register",
      target_type="model",
      target_id_from="model_id",
  )
  def register(model_id: str, name: str):
      ...


  # 模型下线
  @audit(
      action="model.retire",
      target_type="model",
      target_id_from="model_id",
  )
  def retire(model_id: str, version: str, reason: str):
      ...


  # 自定义 target_id
  @audit(
      action="deployment.create",
      target_type="deployment",
      target_id_func=lambda p: f"{p['model_id']}-{p['version']}"
  )
  def deploy(model_id: str, version: str):
      ...
"""

from functools import wraps
from inspect import signature
from typing import Optional, Callable

from datamind.db.core.uow import UnitOfWork
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
        action: 操作类型（resource.verb）
        target_type: 目标类型
        target_id_from: 从函数参数中提取 target_id
        target_id_func: 自定义 target_id 生成函数
    """

    def decorator(func):
        sig = signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # 绑定参数
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            params = {
                k: v for k, v in bound.arguments.items()
                if k != "self"
            }

            # 生成 target_id
            if target_id_func:
                target_id = target_id_func(params)
            elif target_id_from:
                target_id = params.get(target_id_from)
            else:
                target_id = None

            try:
                result = func(*args, **kwargs)

                # 成功审计
                with UnitOfWork() as uow:
                    recorder = AuditRecorder(uow.audit())

                    recorder.record(
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        after={
                            "result": result,
                        },
                        context={
                            "params": params,
                        },
                    )

                return result

            except Exception as e:
                # 异常审计
                with UnitOfWork() as uow:
                    recorder = AuditRecorder(uow.audit())

                    recorder.record(
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        after={
                            "error": str(e),
                        },
                        context={
                            "params": params,
                        },
                    )

                raise

        return wrapper

    return decorator