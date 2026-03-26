# datamind/core/ml/scorecard.py

"""标准评分卡

基于 PDO (Points to Double the Odds) 的评分卡转换。

核心功能：
  - score: 概率转评分
  - probability: 评分转概率（可逆，不截断）
  - get_params: 获取评分卡参数

特性：
  - PDO 标准：遵循银行业标准的 PDO 评分卡公式
  - 双向可逆：probability(score(prob)) ≈ prob
  - 方向支持：支持 lower_better 和 higher_better
  - 中心点支持：支持自定义基准几率（base_odds）
  - 参数校验：direction 合法性校验
  - 性能优化：factor 使用 cached_property
"""

import math
from dataclasses import dataclass
from functools import cached_property
from typing import Dict, Any

# 默认参数
DEFAULT_BASE_SCORE = 600
DEFAULT_PDO = 50
DEFAULT_MIN_SCORE = 300
DEFAULT_MAX_SCORE = 950
DEFAULT_BASE_ODDS = 1.0
DEFAULT_DIRECTION = "lower_better"

# 方向常量
DIRECTION_LOWER_BETTER = "lower_better"    # 分数越低风险越高（分高好）
DIRECTION_HIGHER_BETTER = "higher_better"  # 分数越高风险越高（分低好）

# 有效方向列表
VALID_DIRECTIONS = {DIRECTION_LOWER_BETTER, DIRECTION_HIGHER_BETTER}


@dataclass
class Scorecard:
    """标准评分卡"""

    base_score: int = DEFAULT_BASE_SCORE
    pdo: int = DEFAULT_PDO
    min_score: int = DEFAULT_MIN_SCORE
    max_score: int = DEFAULT_MAX_SCORE
    direction: str = DEFAULT_DIRECTION
    base_odds: float = DEFAULT_BASE_ODDS

    def __post_init__(self):
        """参数校验"""
        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"无效的 direction: {self.direction}，"
                f"有效值: {list(VALID_DIRECTIONS)}"
            )

        if self.pdo <= 0:
            raise ValueError(f"pdo 必须大于 0，当前值: {self.pdo}")

        if self.base_odds <= 0:
            raise ValueError(f"base_odds 必须大于 0，当前值: {self.base_odds}")

        if self.min_score >= self.max_score:
            raise ValueError(f"min_score ({self.min_score}) 必须小于 max_score ({self.max_score})")

    @cached_property
    def factor(self) -> float:
        """
        计算因子 = PDO / ln(2)

        返回:
            因子值
        """
        return self.pdo / math.log(2)

    @cached_property
    def base_log_odds(self) -> float:
        """
        计算基准对数几率

        返回:
            ln(base_odds)
        """
        return math.log(self.base_odds)

    def score(self, prob: float) -> float:
        """
        概率转评分

        公式：
            score = base_score - factor × (log_odds - base_log_odds)   [lower_better]
            score = base_score + factor × (log_odds - base_log_odds)   [higher_better]

        其中：
            - lower_better: 概率越高，分数越低（好客户分数高）
            - higher_better: 概率越高，分数越高（高风险分数高）

        参数:
            prob: 违约概率 (0-1)

        返回:
            信用评分（不裁剪，保留完整精度）
        """
        eps = 1e-10
        prob = max(min(prob, 1.0 - eps), eps)
        odds = prob / (1.0 - prob)
        log_odds = math.log(odds)

        if self.direction == DIRECTION_LOWER_BETTER:
            # 分高好：概率越高，分数越低
            score = float(self.base_score) - self.factor * (log_odds - self.base_log_odds)
        else:
            # 分低好：概率越高，分数越高
            score = float(self.base_score) + self.factor * (log_odds - self.base_log_odds)

        return score

    def probability(self, score: float) -> float:
        """
        评分转概率（可逆，不截断）

        保证：probability(score(prob)) ≈ prob

        参数:
            score: 信用评分

        返回:
            违约概率 (0-1)
        """
        if self.direction == DIRECTION_LOWER_BETTER:
            log_odds = self.base_log_odds + (float(self.base_score) - score) / self.factor
        else:
            log_odds = self.base_log_odds + (score - float(self.base_score)) / self.factor

        odds = math.exp(log_odds)
        prob = odds / (1.0 + odds)

        eps = 1e-10
        return max(min(prob, 1.0 - eps), eps)

    def clip_score(self, score: float) -> float:
        """
        裁剪评分到 [min_score, max_score]（仅用于展示）

        注意：此方法会破坏可逆性，仅用于对外输出

        参数:
            score: 原始评分

        返回:
            裁剪后的评分
        """
        return max(float(self.min_score), min(float(self.max_score), score))

    def get_params(self) -> Dict[str, Any]:
        """
        获取评分卡参数

        返回:
            参数字典
        """
        return {
            'base_score': self.base_score,
            'pdo': self.pdo,
            'min_score': self.min_score,
            'max_score': self.max_score,
            'direction': self.direction,
            'base_odds': self.base_odds,
            'factor': self.factor,
            'base_log_odds': self.base_log_odds,
            'formula': self._get_formula()
        }

    def _get_formula(self) -> str:
        """获取评分公式描述"""
        if self.direction == DIRECTION_LOWER_BETTER:
            sign = "-"
        else:
            sign = "+"

        return f"score = {self.base_score} {sign} {self.factor:.2f} × ln(odds / {self.base_odds})"


class ScorecardPresets:
    """评分卡预设配置"""

    # 标准配置（分高好）
    STANDARD = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=DEFAULT_PDO,
        min_score=DEFAULT_MIN_SCORE,
        max_score=DEFAULT_MAX_SCORE,
        direction=DIRECTION_LOWER_BETTER
    )

    # 高区分度配置（适合风险分布集中的客群）
    HIGH_DISCRIMINATION = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=60,
        min_score=250,
        max_score=1000,
        direction=DIRECTION_LOWER_BETTER
    )

    # 保守配置（评分范围更窄）
    CONSERVATIVE = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=40,
        min_score=400,
        max_score=850,
        direction=DIRECTION_LOWER_BETTER
    )

    # 反欺诈专用（分低好，高风险高分）
    FRAUD = Scorecard(
        base_score=DEFAULT_BASE_SCORE,
        pdo=50,
        min_score=0,
        max_score=1000,
        direction=DIRECTION_HIGHER_BETTER
    )