# datamind/core/__init__.py

"""核心模块

提供模型能力、统一推理、评分、评分转换和评分贡献分解能力。

核心功能：
  - Inference: 统一模型推理接口
  - BaseScorer: 评分组件基类
  - ScoreTransformer: 评分转换器
  - Scorer: 评分器
  - LRContrib: 逻辑回归评分贡献分解器
  - ModelCapability: 模型能力枚举
  - ScorecardCapability: 评分能力枚举

使用示例：
  from datamind.config.scorecard import ScorecardConfig
  from datamind.constants import DataType
  from datamind.core import (
      Inference,
      LRContrib,
      Scorer,
      ScoreTransformer,
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

  transformer = ScoreTransformer(
      config=ScorecardConfig(
          base_score=600,
          base_odds=20,
          pdo=50,
      )
  )

  scorer = Scorer(
      inference=inference,
      transformer=transformer,
  )

  contrib = LRContrib(
      inference=inference,
      transformer=transformer,
  )

  probability = inference.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })

  score = scorer.score({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })

  contributions = contrib.explain({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

from datamind.core.capability import (
    ModelCapability,
    ScorecardCapability,
)
from datamind.core.inference import Inference
from datamind.core.scoring import (
    BaseScorer,
    LRContrib,
    Scorer,
    ScoreTransformer,
)

__all__ = [
    "Inference",
    "BaseScorer",
    "LRContrib",
    "Scorer",
    "ScoreTransformer",
    "ModelCapability",
    "ScorecardCapability",
]
