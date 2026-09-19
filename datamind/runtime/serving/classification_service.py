"""分类任务运行时服务

提供二分类模型的在线推理能力。

核心功能：
  - predict: 单条分类预测
  - predict_batch: 批量分类预测

使用示例：
  from datamind.runtime.serving import ClassificationService

  service = ClassificationService(
      runtime_model=runtime_model,
      threshold=0.5,
  )

  result = service.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

from collections.abc import Iterable
from typing import Any

import numpy as np

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.inference import Inference
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService


class ClassificationService(BaseRuntimeService):
    """分类任务运行时服务

    基于分类模型和分类阈值生成二分类结果。

    属性：
        SERVICE_TYPE: 服务类型
        threshold: 分类阈值
    """

    SERVICE_TYPE = "classification"

    def __init__(
            self,
            *,
            runtime_model: RuntimeModel,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            threshold: float = 0.5,
    ):
        """初始化分类任务运行时服务

        参数：
            runtime_model: 已加载的运行时模型
            feature_names: 特征名称列表（可选）
            data_types: 特征类型映射（可选）
            threshold: 分类阈值，默认值为 0.5

        异常：
            ValueError: 分类阈值不在 [0, 1] 范围内
            NotImplementedError: 模型不支持概率预测
        """
        if not 0 <= threshold <= 1:
            raise ValueError(
                "threshold 必须在 0 到 1 之间"
            )

        super().__init__(
            runtime_model=runtime_model,
            feature_names=feature_names,
            data_types=data_types,
        )

        self.class_labels = self._resolve_class_labels(
            runtime_model.model
        )
        self.inference = Inference(
            model=runtime_model.model,
            feature_names=self.feature_names,
            data_types=self.data_types,
            positive_class=self.class_labels[1],
        )

        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        self.threshold = float(threshold)

    @staticmethod
    def _resolve_class_labels(
            model: Any,
    ) -> tuple[Any, Any]:
        """解析模型的负类和正类标签。"""
        classes = getattr(model, "classes_", None)

        if (
                not isinstance(classes, Iterable)
                or isinstance(classes, (str, bytes))
        ):
            return 0, 1

        class_values = tuple(classes)

        if len(class_values) != 2:
            return 0, 1

        return (
            ClassificationService._normalize_class_label(
                class_values[0]
            ),
            ClassificationService._normalize_class_label(
                class_values[1]
            ),
        )

    @staticmethod
    def _normalize_class_label(label: Any) -> Any:
        """将 NumPy 类别标量转换为 Python 标量。"""
        return (
            label.item()
            if isinstance(label, np.generic)
            else label
        )

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取服务能力集"""
        return self.inference.get_capabilities()

    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """单条分类预测

        参数：
            features: 特征字典

        返回：
            分类预测结果，包含分类标签、预测概率、分类阈值和模型运行信息

        异常：
            ValueError: 输入特征或分类结果无效
            TypeError: 特征类型或预测结果结构无效
        """
        if not features:
            raise ValueError(
                "features 不能为空"
            )

        self._validate_feature_types(features)

        probability = self.inference.predict(
            features
        )

        if isinstance(probability, list):
            raise TypeError(
                "单条分类预测返回了批量结果"
            )

        probability_value = float(
            probability
        )

        self.touch()

        return self.build_result(
            self._build_classification_result(
                probability_value
            )
        )

    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量分类预测

        参数：
            features_list: 特征字典列表

        返回：
            批量分类预测结果，包含预测结果列表、样本数量和模型运行信息。
            每条预测结果包含分类标签、预测概率和分类阈值。
            输入为空列表时，返回空结果列表，样本数量为 0。

        异常：
            ValueError: 输入特征或分类结果无效
            TypeError: 特征类型或预测结果结构无效
            NotImplementedError: 模型不支持批量推理
        """
        self.require_capability(
            ModelCapability.BATCH_PREDICT
        )

        if not features_list:
            return self.build_result({
                "count": 0,
                "predictions": [],
            })

        self._validate_batch_feature_types(features_list)

        probabilities = self.inference.predict(
            features_list
        )

        if not isinstance(probabilities, list):
            raise TypeError(
                "批量分类预测未返回列表结果"
            )

        predictions = [
            self._build_classification_result(
                float(probability)
            )
            for probability in probabilities
        ]

        self.touch()

        return self.build_result({
            "count": len(predictions),
            "predictions": predictions,
        })

    def _build_classification_result(
            self,
            probability: float,
    ) -> dict[str, Any]:
        """构造包含类别标签的分类结果。"""
        prediction = self._classify(
            probability
        )

        return {
            "prediction": prediction,
            "label": self.class_labels[prediction],
            "probability": probability,
            "threshold": self.threshold,
        }

    def _classify(
            self,
            probability: float,
    ) -> int:
        """根据分类阈值生成分类标签

        参数：
            probability: 预测概率

        返回：
            预测概率大于或等于分类阈值时返回 1，否则返回 0
        """
        return int(
            probability >= self.threshold
        )
