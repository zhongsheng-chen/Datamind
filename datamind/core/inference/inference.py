"""统一推理接口

封装模型适配器创建、概率预测、对数几率预测、特征转换、
特征校验、特征重要性和能力查询。

核心功能：
  - predict: 概率预测
  - predict_logit: 对数几率预测
  - transform: 特征转换
  - transform_batch: 批量特征转换
  - validate_features: 特征校验
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取模型能力集
  - has_capability: 检查模型能力
  - require_capability: 校验模型能力

使用示例：
  import numpy as np
  from sklearn.linear_model import LogisticRegression

  from datamind.constants import DataType
  from datamind.core.capability import ModelCapability
  from datamind.core.inference import Inference

  X_train = np.array([
      [25, 80000, 0.20, 0.25, 0],
      [45, 150000, 0.38, 0.62, 2],
      [32, 100000, 0.28, 0.35, 0],
      [50, 180000, 0.42, 0.70, 3],
  ])

  y_train = np.array([
      1,
      0,
      1,
      0,
  ])

  model = LogisticRegression()
  model.fit(
      X_train,
      y_train,
  )

  inference = Inference(
      model=model,
      feature_names=[
          "age",
          "annual_income",
          "debt_to_income_ratio",
          "credit_utilization_ratio",
          "delinquency_count",
      ],
      data_types={
          "age": DataType.NUMERIC,
          "annual_income": DataType.NUMERIC,
          "debt_to_income_ratio": DataType.NUMERIC,
          "credit_utilization_ratio": DataType.NUMERIC,
          "delinquency_count": DataType.NUMERIC,
      },
      positive_class=1,
  )

  features = {
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  }

  probability = inference.predict(
      features
  )

  if inference.has_capability(
      ModelCapability.PREDICT_LOG_ODDS
  ):
      log_odds = inference.predict_logit(
          features
      )
"""

from typing import Any

import numpy as np

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.inference.adapters.base import (
    BaseModelAdapter,
    PredictionInput,
    PredictionResult,
)
from datamind.core.inference.adapters.factory import ModelAdapterFactory


class Inference:
    """统一模型推理接口"""

    def __init__(
            self,
            model: Any,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            positive_class: Any = 1,
    ) -> None:
        """初始化推理实例

        参数：
            model: 已训练模型
            feature_names: 特征名称列表（可选）
            data_types: 特征类型映射（可选）
            positive_class: 正类标签，默认值为 1
        """
        self.adapter: BaseModelAdapter = (
            ModelAdapterFactory.create(
                model=model,
                feature_names=feature_names,
                data_types=data_types,
                positive_class=positive_class,
            )
        )

    def predict(
            self,
            X: PredictionInput,
    ) -> PredictionResult:
        """概率预测"""
        return self.adapter.predict(
            X
        )

    def predict_logit(
            self,
            X: PredictionInput,
    ) -> PredictionResult:
        """对数几率预测"""
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        return self.adapter.predict_logit(
            X
        )

    def transform(
            self,
            X: dict[str, Any],
    ) -> np.ndarray:
        """特征转换"""
        return self.adapter.to_array(
            X
        )

    def transform_batch(
            self,
            X: list[dict[str, Any]],
    ) -> np.ndarray:
        """批量特征转换"""
        return self.adapter.to_array_batch(
            X
        )

    def validate_features(
            self,
            X: dict[str, Any],
    ) -> tuple[
        list[str],
        list[tuple[str, str, str]],
    ]:
        """特征校验"""
        return self.adapter.validate_features(
            X
        )

    def get_feature_importance(
            self,
    ) -> dict[str, float]:
        """获取特征重要性"""
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        return self.adapter.get_feature_importance()

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取模型能力集"""
        return self.adapter.get_capabilities()

    def has_capability(
            self,
            capability: ModelCapability,
    ) -> bool:
        """检查模型能力"""
        return self.adapter.has_capability(
            capability
        )

    def require_capability(
            self,
            capability: ModelCapability,
    ) -> None:
        """校验模型能力"""
        self.adapter.require_capability(
            capability
        )
