# datamind/runtime/serving/factory.py

"""运行时服务工厂

根据模型任务类型创建对应的运行时服务。

核心功能：
  - RuntimeServiceFactory: 运行时服务工厂
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
      "age": 30,
      "income": 50000,
  })
"""

from typing import Any

from datamind.config.scorecard import ScorecardConfig
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
            scorecard_config: ScorecardConfig | dict[str, Any] | None = None,
    ) -> BaseRuntimeService:
        """创建运行时服务

        参数：
            runtime_model: 已加载运行时模型
            task_type: 任务类型，为 None 时从 metadata 获取
            feature_names: 特征名称列表
            data_types: 特征类型映射
            threshold: 分类阈值
            scorecard_config: 评分配置

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
            resolved_threshold = (
                cls._parse_threshold(
                    threshold
                )
                if threshold is not None
                else cls._resolve_threshold(
                    runtime_model
                )
            )

            if resolved_threshold is None:
                resolved_threshold = 0.5

            return ClassificationService(
                runtime_model=runtime_model,
                feature_names=feature_names,
                data_types=data_types,
                threshold=resolved_threshold,
            )

        if resolved_task_type == "scoring":
            return ScoringService(
                runtime_model=runtime_model,
                feature_names=feature_names,
                data_types=data_types,
                scorecard_config=scorecard_config,
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
            runtime_model: RuntimeModel,
    ) -> float:
        """解析分类阈值

        优先级：
          - metadata.threshold
          - metadata.config.threshold
          - 默认值 0.5

        参数：
            runtime_model: 运行时模型

        返回：
            分类阈值

        异常：
            ValueError:
                threshold 类型错误
                threshold 无法转换为浮点数
                threshold 超出合法范围
        """
        metadata = (
                runtime_model.metadata
                or {}
        )

        threshold = cls._parse_threshold(
            metadata.get(
                "threshold"
            )
        )

        if threshold is not None:
            return threshold

        config = metadata.get(
            "config"
        )

        if isinstance(
                config,
                dict,
        ):
            threshold = cls._parse_threshold(
                config.get(
                    "threshold"
                )
            )

            if threshold is not None:
                return threshold

        return 0.5

    @staticmethod
    def _parse_threshold(
            value: Any,
    ) -> float | None:
        """解析分类阈值

        参数：
            value: 原始阈值

        返回：
            浮点型阈值；
            值为 None 时返回 None

        异常：
            ValueError:
                阈值类型错误
                阈值无法转换为浮点数
                阈值不在 0 到 1 范围内
        """
        if value is None:
            return None

        if isinstance(
                value,
                bool,
        ):
            raise ValueError(
                "threshold 不能是布尔值"
            )

        if not isinstance(
                value,
                (int, float, str),
        ):
            raise ValueError(
                "threshold 类型无效: "
                f"{type(value).__name__}"
            )

        try:
            threshold = float(
                value
            )
        except ValueError as exc:
            raise ValueError(
                "threshold 无法转换为浮点数: "
                f"{value}"
            ) from exc

        if not 0 <= threshold <= 1:
            raise ValueError(
                "threshold 必须在 0 到 1 之间，"
                f"当前值: {threshold}"
            )

        return threshold
