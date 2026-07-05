# datamind/runtime/serving/__init__.py

"""运行时模型服务模块

提供不同任务类型的模型运行服务。

核心功能：
  - BaseRuntimeService: 运行时服务基类
  - ClassificationService: 分类模型运行服务
  - ScoringService: 评分模型运行服务
  - RuntimeServiceFactory: 运行时服务工厂

使用示例：
  from datamind.runtime.serving import RuntimeServiceFactory

  service = RuntimeServiceFactory.create(
      runtime_model=runtime_model,
  )

  result = service.predict(features)
"""

from datamind.runtime.serving.base import BaseRuntimeService
from datamind.runtime.serving.classification_service import (
    ClassificationService,
)
from datamind.runtime.serving.scoring_service import (
    ScoringService,
)
from datamind.runtime.serving.factory import (
    RuntimeServiceFactory,
)

__all__ = [
    "BaseRuntimeService",
    "ClassificationService",
    "ScoringService",
    "RuntimeServiceFactory",
]