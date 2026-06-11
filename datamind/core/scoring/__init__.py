# datamind/core/scoring/__init__.py

"""评分模块

提供评分卡相关的核心功能：
    - 评分转换器：Logit、Odds、Probability 与 Score 之间的转换
    - 评分器：基于模型预测结果计算评分
    - 特征贡献分解器：逻辑回归模型的特征贡献分解
    - 评分组件基类：定义评分组件统一接口规范

使用示例：
    from datamind.core.scoring import Scorer, ScoreTransformer, LRContrib

    # 创建评分转换器
    transformer = ScoreTransformer()
    score = transformer.probability_to_score(0.3)

    # 模型评分
    scorer = Scorer(inference)
    score = scorer.score(features)

    # 特征贡献分解
    contrib = LRContrib(inference)
    explanation = contrib.explain(features)
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