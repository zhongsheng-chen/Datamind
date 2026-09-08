"""审计组件

对外提供审计装饰器、记录器、服务和失败策略。

核心功能：
  - audit: 审计装饰器
  - AuditRecorder: 审计记录器
  - AuditService: 审计服务
  - AuditFailureMode: 审计失败处理模式
  - AuditResult: 审计记录结果
"""

from importlib import import_module
from typing import (
    Any,
    Final,
)

_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "AuditFailureMode": (
        "datamind.audit.policy",
        "AuditFailureMode",
    ),
    "AuditRecorder": (
        "datamind.audit.recorder",
        "AuditRecorder",
    ),
    "AuditResult": (
        "datamind.audit.service",
        "AuditResult",
    ),
    "AuditService": (
        "datamind.audit.service",
        "AuditService",
    ),
    "audit": (
        "datamind.audit.decorator",
        "audit",
    ),
}

__all__ = list(
    _EXPORTS
)


def __getattr__(name: str) -> Any:
    """按需加载包级公共 API"""
    target = _EXPORTS.get(name)

    if target is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    module_name, attribute_name = target
    value = getattr(
        import_module(module_name),
        attribute_name,
    )
    globals()[name] = value

    return value
