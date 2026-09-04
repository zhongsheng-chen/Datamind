# datamind/runtime/serving/scoring_service.py

"""评分卡运行服务

提供评分卡的在线评分和决策能力。

核心功能：
  - ScoringService: 评分卡运行服务
  - predict: 单条评分
  - predict_batch: 批量评分

使用示例：
  from datamind.runtime.serving import ScoringService

  service = ScoringService(
      runtime_model=runtime_model,
      threshold=600.0,
  )

  result = service.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

import math
from typing import Any

import numpy as np
import pandas as pd
from optbinning import Scorecard

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.models.enums import DecisionResult
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService


class ScoringService(BaseRuntimeService):
    """评分卡运行服务

    输出违约概率和信用分，并根据评分决策阈值生成通过或拒绝结果。

    属性：
        SERVICE_TYPE: 服务类型
        threshold: 评分决策阈值
    """

    SERVICE_TYPE = "scoring"

    def __init__(
            self,
            *,
            runtime_model: RuntimeModel,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            threshold: float = 600.0,
    ) -> None:
        """初始化评分卡运行服务

        参数：
            runtime_model: 已加载的运行时模型
            feature_names: 特征名称列表
            data_types: 特征类型映射
            threshold: 评分决策阈值

        异常：
            TypeError: 模型类型不匹配
            ValueError: threshold 不是有限数值
            NotImplementedError: 模型不支持概率预测
        """
        super().__init__(
            runtime_model=runtime_model,
            feature_names=feature_names,
            data_types=data_types,
        )
        self.require_capability(ModelCapability.PREDICT_PROBA)

        model = runtime_model.model

        if not isinstance(model, Scorecard):
            raise TypeError(
                "模型类型不匹配："
                f"期望 {Scorecard.__name__}，实际 "
                f"{type(model).__name__}"
            )

        self.threshold = float(threshold)

        if not math.isfinite(self.threshold):
            raise ValueError("threshold 必须是有限数值")

    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """单条评分

        参数：
            features: 特征字典

        返回：
            评分结果，包含违约概率、信用分、决策和决策阈值

        异常：
            ValueError: features 为空
            TypeError: 概率预测结果类型异常
        """
        if not features:
            raise ValueError("features 不能为空")

        probability = self.inference.predict(features)

        if isinstance(probability, list):
            raise TypeError("单条评分返回了批量概率结果")

        score = self._score([features])[0]
        self.touch()

        return self.build_result({
            "probability": float(probability),
            "score": score,
            "decision": self._decide(score),
            "threshold": self.threshold,
        })

    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量评分

        参数：
            features_list: 特征字典列表

        返回：
            批量评分结果及样本数量

        异常：
            TypeError: 概率预测结果类型异常
            RuntimeError: 概率和评分结果数量不一致
            NotImplementedError: 模型不支持批量推理
        """
        self.require_capability(ModelCapability.BATCH_PREDICT)

        if not features_list:
            return self.build_result({
                "count": 0,
                "predictions": [],
            })

        probabilities = self.inference.predict(features_list)

        if not isinstance(probabilities, list):
            raise TypeError("批量评分未返回概率列表")

        scores = self._score(features_list)

        if len(probabilities) != len(scores):
            raise RuntimeError("概率与评分结果数量不一致")

        predictions = [
            {
                "probability": float(probability),
                "score": score,
                "decision": self._decide(score),
                "threshold": self.threshold,
            }
            for probability, score in zip(probabilities, scores)
        ]
        self.touch()

        return self.build_result({
            "count": len(predictions),
            "predictions": predictions,
        })

    def _score(
            self,
            features_list: list[dict[str, Any]],
    ) -> list[float]:
        """调用模型评分接口

        参数：
            features_list: 特征字典列表

        返回：
            信用分列表
        """
        frame = pd.DataFrame(
            features_list,
            columns=self.feature_names,
        )
        values = np.asarray(
            self.runtime_model.model.score(frame),
            dtype=float,
        ).reshape(-1)
        return [float(value) for value in values]

    def _decide(self, score: float) -> str:
        """根据评分阈值生成业务决策

        参数：
            score: 信用分

        返回：
            approve 或 reject
        """
        return (
            DecisionResult.APPROVE.value
            if score >= self.threshold
            else DecisionResult.REJECT.value
        )
