# datamind/runtime/serving/factory.py

"""运行时服务工厂

根据模型任务类型创建对应的运行时服务。

核心功能：
  - create: 根据 task_type 创建运行时服务

支持的任务类型：
  - classification: 分类模型服务
  - scoring: 评分模型服务

使用示例：
  from datamind.runtime.serving.factory import RuntimeServiceFactory

  service = RuntimeServiceFactory.create(
      runtime_model=runtime_model,
      task_type="scoring",
  )

  result = service.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

from typing import Any

from datamind.config.classification import ClassificationConfig
from datamind.config.scoring import ScoringConfig
from datamind.constants import DataType
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService
from datamind.runtime.serving.classification_service import (
    ClassificationService,
)
from datamind.runtime.serving.scoring_service import (
    ScoringService,
)


class RuntimeServiceFactory:
    """运行时服务工厂

    根据任务类型创建对应的运行时服务。
    """

    SUPPORTED_TASK_TYPES = {
        "classification",
        "scoring",
    }

    @classmethod
    def create(
            cls,
            *,
            runtime_model: RuntimeModel,
            task_type: str | None = None,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            threshold: float | None = None,
    ) -> BaseRuntimeService:
        """创建运行时服务

        参数：
            runtime_model: 已加载运行时模型
            task_type: 任务类型，为 None 时从 metadata 获取
            feature_names: 特征名称列表
            data_types: 特征类型映射
            threshold: 分类阈值

        返回：
            具体运行时服务实例

        异常：
            ValueError:
                runtime_model 为空
                task_type 为空
                task_type 不支持
                threshold 类型错误
                threshold 超出合法范围
        """
        if runtime_model is None:
            raise ValueError(
                "runtime_model 不能为空"
            )

        resolved_task_type = cls._resolve_task_type(
            runtime_model=runtime_model,
            task_type=task_type,
        )

        if resolved_task_type == "classification":
            resolved_threshold = cls._resolve_threshold(
                runtime_model=runtime_model,
                threshold=threshold,
                config_type=ClassificationConfig,
            )

            return ClassificationService(
                runtime_model=runtime_model,
                feature_names=feature_names,
                data_types=data_types,
                threshold=resolved_threshold,
            )

        if resolved_task_type == "scoring":
            resolved_threshold = cls._resolve_threshold(
                runtime_model=runtime_model,
                threshold=threshold,
                config_type=ScoringConfig,
            )
            return ScoringService(
                runtime_model=runtime_model,
                feature_names=feature_names,
                data_types=data_types,
                threshold=resolved_threshold,
            )

        raise ValueError(
            f"不支持的任务类型: {resolved_task_type}"
        )

    @classmethod
    def _resolve_task_type(
            cls,
            *,
            runtime_model: RuntimeModel,
            task_type: str | None,
    ) -> str:
        """解析任务类型

        优先级：
          - 显式传入 task_type
          - RuntimeModel metadata 中的 task_type

        参数：
            runtime_model: 运行时模型
            task_type: 显式任务类型

        返回：
            标准化后的任务类型

        异常：
            ValueError: task_type 为空或不支持
        """
        resolved: Any = task_type

        if resolved is None:
            metadata = (
                    runtime_model.metadata
                    or {}
            )

            resolved = metadata.get(
                "task_type"
            )

        if resolved is None:
            raise ValueError(
                "task_type 不能为空，"
                "请显式传入或在 RuntimeModel.metadata 中设置 task_type"
            )

        resolved_task_type = str(
            resolved
        ).strip().lower()

        if not resolved_task_type:
            raise ValueError(
                "task_type 不能为空，"
                "请显式传入或在 RuntimeModel.metadata 中设置 task_type"
            )

        if resolved_task_type not in cls.SUPPORTED_TASK_TYPES:
            supported = ", ".join(
                sorted(
                    cls.SUPPORTED_TASK_TYPES
                )
            )

            raise ValueError(
                f"不支持的任务类型: {resolved_task_type}，"
                f"支持类型: {supported}"
            )

        return resolved_task_type

    @classmethod
    def _resolve_threshold(
            cls,
            *,
            runtime_model: RuntimeModel,
            threshold: float | None,
            config_type: type[
                ClassificationConfig | ScoringConfig
            ],
    ) -> float:
        """解析任务决策阈值

        优先级：
          - 显式传入的 threshold
          - RuntimeModel metadata.threshold
          - 任务配置默认值

        参数：
            runtime_model: 运行时模型
            threshold: 显式传入的决策阈值
            config_type: 任务配置类型

        返回：
            决策阈值

        异常：
            ValueError:
                threshold 类型或取值错误
        """
        if isinstance(threshold, bool):
            raise ValueError("threshold 不能是布尔值")

        metadata = runtime_model.metadata or {}
        resolved_threshold = (
            threshold
            if threshold is not None
            else metadata.get("threshold")
        )

        if resolved_threshold is None:
            return config_type().threshold

        return config_type(
            threshold=resolved_threshold
        ).threshold
