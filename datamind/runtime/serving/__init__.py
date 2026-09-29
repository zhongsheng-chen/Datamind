"""模型运行时服务组件.

提供分类预测、评分计算和运行时服务创建能力。

核心功能：
  - BaseRuntimeService: 运行时服务基类
  - ClassificationService: 分类任务运行时服务
  - ScoringService: 评分任务运行时服务
  - RuntimeServiceFactory: 运行时服务工厂

使用示例：
  from datamind.runtime.serving import RuntimeServiceFactory

  service = RuntimeServiceFactory.create(
      runtime_model=runtime_model,
      task_type="classification",
  )
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from datamind.runtime.serving.base import BaseRuntimeService

if TYPE_CHECKING:
    from datamind.runtime.serving.classification_service import (
        ClassificationService,
    )
    from datamind.runtime.serving.factory import RuntimeServiceFactory
    from datamind.runtime.serving.scoring_service import ScoringService


_SERVICE_EXPORTS = {
    "ClassificationService": (
        "datamind.runtime.serving.classification_service",
        "ClassificationService",
    ),
    "RuntimeServiceFactory": (
        "datamind.runtime.serving.factory",
        "RuntimeServiceFactory",
    ),
    "ScoringService": (
        "datamind.runtime.serving.scoring_service",
        "ScoringService",
    ),
}

__all__ = [
    "BaseRuntimeService",
    "ClassificationService",
    "ScoringService",
    "RuntimeServiceFactory",
]


def __getattr__(name: str) -> Any:
    """按需加载具体运行时服务."""
    target = _SERVICE_EXPORTS.get(name)
    if target is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    module_name, attribute_name = target
    exported = getattr(import_module(module_name), attribute_name)
    globals()[name] = exported
    return exported
