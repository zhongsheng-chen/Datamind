# datamind/core/scoring/scorer.py

"""评分器

提供评分计算能力，支持批量评分。

核心功能：
  - score: 计算评分
  - score_batch: 批量计算评分
  - probability_to_score: 违约概率转评分
  - logit_to_score: Logit 转评分

使用示例：
  import numpy as np
  from sklearn.linear_model import LogisticRegression

  from datamind.core.inference import Inference
  from datamind.core.scoring.scorer import Scorer

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
      positive_class=1,
  )

  scorer = Scorer(
      inference=inference
  )

  score = scorer.score({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })

  scores = scorer.score_batch([
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

from typing import ClassVar

import structlog

from datamind.core.capability import (
    ModelCapability,
    ScorecardCapability,
)
from datamind.core.inference import Inference
from datamind.core.model.adapters.base import (
    PredictionInput,
    PredictionResult,
)
from datamind.core.scoring.base import BaseScorer
from datamind.core.scoring.transformer import ScoreTransformer

logger = structlog.get_logger(__name__)


class Scorer(BaseScorer):
    """评分器"""

    SUPPORTED_CAPABILITIES: ClassVar[
        ScorecardCapability
    ] = (
        ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    def __init__(
            self,
            inference: Inference,
            transformer: ScoreTransformer | None = None,
    ) -> None:
        """初始化评分器

        参数：
            inference: 统一模型推理接口
            transformer: 评分转换器，为 None 时使用默认配置

        异常：
            NotImplementedError: 模型不支持 Logit 预测
        """
        inference.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        self.inference = inference
        self.transformer = (
            transformer
            if transformer is not None
            else ScoreTransformer()
        )

        transformer_name = str(
            type(
                self.transformer
            ).__name__
        )

        logger.debug(
            "初始化评分器",
            transformer=transformer_name,
        )

    def score(
            self,
            X: PredictionInput,
    ) -> float:
        """计算评分"""
        self.require_capability(
            ScorecardCapability.SCORECARD_TOTAL_SCORE
        )

        logit = self._require_scalar_logit(
            self.inference.predict_logit(
                X
            )
        )

        result = self.transformer.logit_to_score(
            logit
        )

        logger.debug(
            "评分完成",
            logit=logit,
            score=result,
        )

        return result

    def score_batch(
            self,
            X: PredictionInput,
    ) -> list[float]:
        """批量计算评分"""
        self.require_capability(
            ScorecardCapability.SCORECARD_TOTAL_SCORE
        )

        logits = self._require_logit_list(
            self.inference.predict_logit(
                X
            )
        )

        result = [
            self.transformer.logit_to_score(
                logit
            )
            for logit in logits
        ]

        logger.debug(
            "批量评分完成",
            sample_count=len(result),
        )

        return result

    def probability_to_score(
            self,
            probability: float,
    ) -> float:
        """违约概率转评分"""
        self.require_capability(
            ScorecardCapability.SCORECARD_TOTAL_SCORE
        )

        return self.transformer.probability_to_score(
            probability
        )

    def logit_to_score(
            self,
            logit: float,
    ) -> float:
        """Logit 转评分"""
        self.require_capability(
            ScorecardCapability.SCORECARD_TOTAL_SCORE
        )

        return self.transformer.logit_to_score(
            logit
        )

    @staticmethod
    def _require_scalar_logit(
            value: PredictionResult,
    ) -> float:
        """校验并返回标量 Logit"""
        if isinstance(
                value,
                list,
        ):
            raise TypeError(
                "评分接口收到 Logit 列表，"
                "请使用 score_batch"
            )

        return float(
            value
        )

    @staticmethod
    def _require_logit_list(
            values: PredictionResult,
    ) -> list[float]:
        """校验并返回 Logit 列表"""
        if not isinstance(
                values,
                list,
        ):
            raise TypeError(
                "批量评分接口收到标量 Logit，"
                "请使用 score"
            )

        return [
            float(value)
            for value in values
        ]
