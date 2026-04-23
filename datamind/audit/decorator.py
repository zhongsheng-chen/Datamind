# datamind/audit/decorator.py

"""审计装饰器

自动为函数添加审计能力，支持从参数、session 或上下文获取 audit_recorder。

使用示例：
    @audit_action("deployment.deploy", "deployment", target_id_getter=lambda r: r.id)
    def deploy_model(session, deployment_data):
        writer = DeploymentWriter(session)
        return writer.write(**deployment_data)
"""

from functools import wraps
from typing import Optional, Callable, Any


def _safe_dict(obj):
    """安全提取对象的字典表示，排除私有属性"""
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {k: _safe_dict(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_safe_dict(v) for v in obj]

    if hasattr(obj, "__dict__"):
        return {
            k: _safe_dict(v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_")
        }

    return str(obj)


def audit_action(
    action: str,
    target_type: str,
    target_id_getter: Optional[Callable[[Any], str]] = None,
):
    """审计装饰器

    参数：
        action: 操作类型（resource.verb 格式）
        target_type: 目标类型
        target_id_getter: 从函数返回值中提取 target_id 的函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            audit_recorder = kwargs.pop("audit_recorder", None)

            if audit_recorder is None:
                session = args[0] if args else None
                audit_recorder = getattr(session, "audit_recorder", None)

            result = func(*args, **kwargs)

            if audit_recorder:
                target_id = (
                    target_id_getter(result)
                    if target_id_getter
                    else getattr(result, "id", None)
                )

                audit_recorder.record(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    after=_safe_dict(result),
                )

            return result
        return wrapper
    return decorator