# datamind/runtime/serving/scoring_service.py

"""评分卡运行服务

提供评分卡的在线评分和决策能力。

核心功能：
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
        """
        model = runtime_model.model

        if not isinstance(model, Scorecard):
            raise TypeError(
                "模型类型不匹配："
                f"期望 {Scorecard.__name__}，实际 "
                f"{type(model).__name__}"
            )

        super().__init__(
            runtime_model=runtime_model,
            feature_names=feature_names,
            data_types=data_types,
        )
        self.model = model
        self.threshold = float(threshold)

        if not math.isfinite(self.threshold):
            raise ValueError("threshold 必须是有限数值")

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取评分服务能力集"""
        return (
            ModelCapability.PREDICT_PROBA
            | ModelCapability.BATCH_PREDICT
        )

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
            ValueError: features 为空或概率预测结果无效
        """
        if not features:
            raise ValueError("features 不能为空")

        prediction = self._evaluate([features])[0]
        self.touch()

        return self.build_result(prediction)

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
            ValueError: 概率预测结果无效
            RuntimeError: 概率和评分结果数量不一致
            NotImplementedError: 模型不支持批量推理
        """
        self.require_capability(ModelCapability.BATCH_PREDICT)

        if not features_list:
            return self.build_result({
                "count": 0,
                "predictions": [],
            })

        predictions = self._evaluate(features_list)
        self.touch()

        return self.build_result({
            "count": len(predictions),
            "predictions": predictions,
        })

    def _evaluate(
            self,
            features_list: list[dict[str, Any]],
    ) -> list[dict[str, float | str]]:
        """计算评分卡结果

        参数：
            features_list: 特征字典列表

        返回：
            概率、分数、决策和决策阈值列表

        异常：
            RuntimeError: 概率与评分结果数量不一致
        """
        frame = pd.DataFrame(
            features_list,
            columns=self.feature_names,
        )

        probabilities = self._extract_probabilities(
            self.model.predict_proba(frame),
            expected_count=len(frame),
        )
        scores = np.asarray(
            self.model.score(frame),
            dtype=float,
        ).reshape(-1)

        if len(probabilities) != len(scores):
            raise RuntimeError(
                "概率与评分结果数量不一致"
            )

        return [
            {
                "probability": probability,
                "score": float(score),
                "decision": self._decide(
                    float(score)
                ),
                "threshold": self.threshold,
            }
            for probability, score in zip(
                probabilities,
                scores,
            )
        ]

    def _extract_probabilities(
            self,
            values: Any,
            *,
            expected_count: int,
    ) -> list[float]:
        """提取评分卡违约概率

        参数：
            values: 模型概率预测结果
            expected_count: 期望样本数

        返回：
            违约概率列表

        异常：
            ValueError: 概率预测结果或模型类别无效
        """
        probabilities = np.asarray(
            values,
            dtype=float,
        )

        expected_shape = (expected_count, 2)

        if probabilities.shape != expected_shape:
            raise ValueError(
                "评分卡概率预测结果形状不正确："
                f"期望 {expected_shape}，"
                f"实际 {probabilities.shape}"
            )

        if (
                not np.all(np.isfinite(probabilities))
                or np.any(probabilities < 0)
                or np.any(probabilities > 1)
        ):
            raise ValueError(
                "评分卡概率预测结果必须是 0 到 1 之间的有限数值"
            )

        classes = np.asarray(
            self.model.estimator_.classes_,
            dtype=object,
        ).reshape(-1)
        positive_indices = np.flatnonzero(
            classes == 1
        )

        if len(positive_indices) != 1:
            raise ValueError(
                "评分卡模型类别中不存在唯一的违约标签 1"
            )

        positive_index = int(
            positive_indices[0]
        )

        return [
            float(value)
            for value in probabilities[
                :,
                positive_index,
            ]
        ]

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
