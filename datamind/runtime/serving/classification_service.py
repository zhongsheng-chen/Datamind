# datamind/runtime/serving/classification_service.py

"""分类模型运行服务

提供二分类模型的在线推理能力。

核心功能：
  - ClassificationService: 分类模型运行服务
  - predict: 单条分类预测
  - predict_batch: 批量分类预测

使用示例：
  from datamind.runtime.serving import ClassificationService

  service = ClassificationService(
      runtime_model=runtime_model,
      threshold=0.5
  )

  result = service.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })

  batch_result = service.predict_batch([
      {
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      },
      {
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      },
  ])
"""

from typing import Any

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService


class ClassificationService(BaseRuntimeService):
    """分类模型运行服务

    基于概率预测结果和分类阈值生成二分类结果。

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
        """初始化分类模型服务

        参数：
            runtime_model: 已加载运行时模型
            feature_names: 特征名称列表
            data_types: 特征类型映射
            threshold: 分类阈值，范围 0 到 1

        异常：
            ValueError: threshold 不在合法范围
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

        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        self.threshold = float(threshold)

    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """单条分类预测

        参数：
            features: 特征字典

        返回：
            分类预测结果，包含：
              - prediction
              - probability
              - threshold
              - deployment_id
              - model_id
              - version_id
              - framework
              - service_type

        异常：
            ValueError: features 为空
            TypeError: 推理结果类型异常
        """
        if not features:
            raise ValueError(
                "features 不能为空"
            )

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

        prediction = self._classify(
            probability_value
        )

        self.touch()

        return self.build_result({
            "prediction": prediction,
            "probability": probability_value,
            "threshold": self.threshold,
        })

    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量分类预测

        参数：
            features_list: 特征字典列表

        返回：
            批量分类预测结果，包含：
              - count
              - predictions
              - deployment_id
              - model_id
              - version_id
              - framework
              - service_type

        异常：
            TypeError: 批量推理结果类型异常
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

        probabilities = self.inference.predict(
            features_list
        )

        if not isinstance(probabilities, list):
            raise TypeError(
                "批量分类预测未返回列表结果"
            )

        predictions = [
            {
                "prediction": self._classify(
                    float(probability)
                ),
                "probability": float(probability),
                "threshold": self.threshold,
            }
            for probability in probabilities
        ]

        self.touch()

        return self.build_result({
            "count": len(predictions),
            "predictions": predictions,
        })

    def _classify(
            self,
            probability: float,
    ) -> int:
        """根据概率计算分类标签

        参数：
            probability: 正类概率

        返回：
            分类标签：
              - 0: 负类
              - 1: 正类
        """
        return int(
            probability >= self.threshold
        )
