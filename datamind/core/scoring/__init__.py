# datamind/core/scoring/__init__.py

"""评分模块

提供评分、评分转换和评分贡献分解能力。

核心功能：
  - BaseScorer: 评分组件基类
  - ScoreTransformer: 评分转换器
  - Scorer: 评分器
  - LRContrib: 逻辑回归评分贡献分解器

使用示例：
  from datamind.config.scorecard import ScorecardConfig
  from datamind.core.scoring import (
      LRContrib,
      Scorer,
      ScoreTransformer,
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

from datamind.core.scoring.base import BaseScorer
from datamind.core.scoring.contrib import LRContrib
from datamind.core.scoring.scorer import Scorer
from datamind.core.scoring.transformer import ScoreTransformer

__all__ = [
    "BaseScorer",
    "LRContrib",
    "Scorer",
    "ScoreTransformer",
]
