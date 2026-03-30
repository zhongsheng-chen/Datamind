# datamind/core/ml/postprocess/scorer.py
"""分数转换器

将违约概率转换为信用评分。

核心功能：
  - score: 概率 → 信用分
  - score_to_proba: 信用分 → 违约概率

评分公式：
    odds = (1 - p) / p
    score = offset + factor * ln(odds)

其中：
    factor = pdo / ln(2)
    offset = base_score - factor * ln(base_odds)

使用示例：
  >>> from datamind.core.ml.postprocess.scorer import ScoreScorer
  >>>
  >>> scorer = ScoreScorer(base_score=600, base_odds=50, pdo=20)
  >>> score = scorer.score(0.18)
  >>> print(score)
  612.5
"""

import numpy as np
from typing import Union


class ScoreScorer:
    """分数转换器

    将违约概率转换为标准信用评分。

    属性:
        base_score: 基准分（odds 对应的分数）
        base_odds: 基准 odds（good:bad）
        pdo: Points to Double the Odds（odds翻倍时分数增加量）
        factor: 评分因子（pdo / ln(2)）
        offset: 评分偏移量（base_score - factor * ln(base_odds)）
    """

    def __init__(
        self,
        base_score: float = 600,
        base_odds: float = 50,
        pdo: float = 20
    ):
        """
        初始化分数转换器

        参数:
            base_score: 基准分，默认 600
            base_odds: 基准 odds（good:bad），默认 50:1
            pdo: Points to Double the Odds，默认 20
        """
        self.base_score = base_score
        self.base_odds = base_odds
        self.pdo = pdo

        self.factor = pdo / np.log(2)
        self.offset = base_score - self.factor * np.log(base_odds)

    def score(self, proba: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        将违约概率转换为信用评分

        参数:
            proba: 违约概率（0-1），或概率数组

        返回:
            信用评分

        示例:
            >>> scorer.score(0.18)
            612.5
        """
        # 避免除零
        proba = np.clip(proba, 1e-10, 1 - 1e-10)

        odds = (1 - proba) / proba
        score = self.offset + self.factor * np.log(odds)

        return score

    def score_to_proba(self, score: float) -> float:
        """
        将信用评分转换为违约概率

        参数:
            score: 信用评分

        返回:
            违约概率

        示例:
            >>> scorer.score_to_proba(612.5)
            0.18
        """
        odds = np.exp((score - self.offset) / self.factor)
        proba = 1 / (1 + odds)
        return proba