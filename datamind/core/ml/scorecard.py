# datamind/core/ml/scorecard.py

"""标准评分卡

基于 PDO (Points to Double the Odds) 的评分卡转换。

核心功能：
  - score: 概率转评分
  - probability: 评分转概率
  - get_params: 获取评分卡参数

特性：
  - PDO 标准：遵循银行业标准的 PDO 评分卡公式
  - 方向控制：支持 "lower_better"（分数越低风险越高）和 "higher_better"（分数越高风险越高）
  - 范围裁剪：支持评分上下限裁剪
  - 可配置：支持自定义基准分、PDO、评分范围

评分方向说明：
  - "lower_better"（默认）：违约概率越高，评分越低
    公式：score = base_score - factor × ln(odds)
    示例：p=0.5 → odds=1 → score=600，p=0.7 → odds=2.33 → score=545

  - "higher_better"：违约概率越高，评分越高
    公式：score = base_score + factor × ln(odds)
    示例：p=0.5 → odds=1 → score=600，p=0.7 → odds=2.33 → score=655

使用示例：
    >>> from datamind.core.ml.scorecard import Scorecard, ScorecardPresets
    >>>
    >>> # lower_better（默认）- 分数越低风险越高
    >>> sc = Scorecard(base_score=600, pdo=50, direction="lower_better")
    >>> score = sc.score(0.7)  # 高概率 → 低分数
    >>>
    >>> # higher_better - 分数越高风险越高
    >>> sc = Scorecard(base_score=600, pdo=50, direction="higher_better")
    >>> score = sc.score(0.7)  # 高概率 → 高分数
"""

import math
from dataclasses import dataclass
from typing import Dict, Any


# 评分卡默认参数
DEFAULT_BASE_SCORE = 600
DEFAULT_PDO = 50
DEFAULT_MIN_SCORE = 300
DEFAULT_MAX_SCORE = 950
DEFAULT_DIRECTION = "lower_better"

# 评分方向常量
DIRECTION_LOWER_BETTER = "lower_better"
DIRECTION_HIGHER_BETTER = "higher_better"


@dataclass
class Scorecard:
    """标准评分卡 - 基于 PDO 的评分卡转换

    属性:
        base_score: 基准分数（odds=1:1 时的分数），默认 600
        pdo: Points to Double the Odds，默认 50
        min_score: 最低分数，默认 300
        max_score: 最高分数，默认 950
        direction: 评分方向，默认 "lower_better"
            - "lower_better": 分数越低风险越高（违约概率越高，分数越低）
            - "higher_better": 分数越高风险越高（违约概率越高，分数越高）
    """

    base_score: int = DEFAULT_BASE_SCORE
    pdo: int = DEFAULT_PDO
    min_score: int = DEFAULT_MIN_SCORE
    max_score: int = DEFAULT_MAX_SCORE
    direction: str = DEFAULT_DIRECTION

    @property
    def factor(self) -> float:
        """
        计算评分因子

        factor = PDO / ln(2)

        返回:
            因子值，用于评分计算
        """
        return self.pdo / math.log(2)

    def score(self, prob: float) -> float:
        """
        违约概率转信用评分

        公式：
            lower_better: score = base_score - factor × ln(odds)
            higher_better: score = base_score + factor × ln(odds)

        参数:
            prob: 违约概率 (0-1)

        返回:
            信用评分，范围 [min_score, max_score]
        """
        eps = 1e-10
        p = max(min(prob, 1 - eps), eps)
        odds = p / (1 - p)
        log_odds = math.log(odds)

        if self.direction == DIRECTION_LOWER_BETTER:
            s = self.base_score - self.factor * log_odds
        else:
            s = self.base_score + self.factor * log_odds

        return max(self.min_score, min(self.max_score, s))

    def probability(self, score: float) -> float:
        """
        信用评分转违约概率

        参数:
            score: 信用评分

        返回:
            违约概率 (0-1)
        """
        if score <= self.min_score:
            return 1.0
        if score >= self.max_score:
            return 0.0

        if self.direction == DIRECTION_LOWER_BETTER:
            log_odds = (self.base_score - score) / self.factor
        else:
            log_odds = (score - self.base_score) / self.factor

        odds = math.exp(log_odds)
        return odds / (1 + odds)

    def get_params(self) -> Dict[str, Any]:
        """
        获取评分卡参数

        返回:
            参数字典，包含 base_score, pdo, min_score, max_score, factor, direction, formula
        """
        if self.direction == DIRECTION_LOWER_BETTER:
            formula = f'score = {self.base_score} - {self.factor:.2f} × ln(odds)'
        else:
            formula = f'score = {self.base_score} + {self.factor:.2f} × ln(odds)'

        return {
            'base_score': self.base_score,
            'pdo': self.pdo,
            'min_score': self.min_score,
            'max_score': self.max_score,
            'factor': self.factor,
            'direction': self.direction,
            'formula': formula
        }


class ScorecardPresets:
    """评分卡预设配置

    提供常用的评分卡配置，便于快速使用。

    预设类型：
        STANDARD: 标准配置（lower_better），大多数银行使用
        REVERSE: 反向配置（higher_better），分数越高风险越高
        HIGH_DISCRIMINATION: 高区分度配置（lower_better），适合风险分布集中的客群
        CONSERVATIVE: 保守配置（lower_better），评分范围更窄
    """

    # 标准配置（lower_better，大多数银行使用）
    STANDARD = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=DEFAULT_PDO,
        min_score=DEFAULT_MIN_SCORE,
        max_score=DEFAULT_MAX_SCORE,
        direction=DIRECTION_LOWER_BETTER
    )

    # 反向配置（higher_better，分数越高风险越高）
    REVERSE = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=DEFAULT_PDO,
        min_score=DEFAULT_MIN_SCORE,
        max_score=DEFAULT_MAX_SCORE,
        direction=DIRECTION_HIGHER_BETTER
    )

    # 高区分度配置（lower_better，适合风险分布集中的客群）
    HIGH_DISCRIMINATION = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=60,
        min_score=250,
        max_score=1000,
        direction=DIRECTION_LOWER_BETTER
    )

    # 保守配置（lower_better，评分范围更窄）
    CONSERVATIVE = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=40,
        min_score=400,
        max_score=850,
        direction=DIRECTION_LOWER_BETTER
    )