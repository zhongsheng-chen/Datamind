# datamind/core/scoring/score.py

"""评分卡分数计算模块

将模型输出的违约概率转换为信用分数。

核心功能：
  - to_score: 单条概率转换为信用分数
  - to_score_batch: 批量概率转换为信用分数

特性：
  - PDO/基准分可配置
  - 支持二分类概率输入
  - 保持数值稳定性
  - 支持分数边界裁剪
  - 支持概率剪裁阈值配置
"""

from typing import List, Optional, Tuple
from math import log, exp


class Score:
    """评分卡分数计算器"""

    # 默认参数
    DEFAULT_PDO: float = 50.0
    DEFAULT_BASE_SCORE: float = 600.0
    DEFAULT_BASE_ODDS: float = 20.0
    DEFAULT_MIN_SCORE: float = 0.0
    DEFAULT_MAX_SCORE: float = 1000.0
    DEFAULT_MIN_PROB: float = 1e-6
    DEFAULT_MAX_PROB: float = 1 - 1e-6

    def __init__(
        self,
        pdo: Optional[float] = None,
        base_score: Optional[float] = None,
        base_odds: Optional[float] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        min_prob: Optional[float] = None,
        max_prob: Optional[float] = None
    ):
        """
        初始化评分卡分数计算器

        参数:
            pdo: 分数翻倍点（每增加PDO点，odds翻倍），默认 50
            base_score: 基准分数，对应base_odds的分数，默认 600
            base_odds: 基准odds（坏账概率/好账概率），默认 20
            min_score: 最低分数限制，默认 0
            max_score: 最高分数限制，默认 1000
            min_prob: 概率最小值剪裁阈值，默认 1e-6
            max_prob: 概率最大值剪裁阈值，默认 1 - 1e-6

        公式:
            score = offset + factor * ln(odds)
            factor = pdo / ln(2)
            offset = base_score - factor * ln(base_odds)

        示例:
            >>> scorer = Score(pdo=50, base_score=600, base_odds=20)
            >>> scorer.to_score(0.02)
            712.5
        """
        # 设置参数（使用默认值）
        self.pdo = pdo if pdo is not None else self.DEFAULT_PDO
        self.base_score = base_score if base_score is not None else self.DEFAULT_BASE_SCORE
        self.base_odds = base_odds if base_odds is not None else self.DEFAULT_BASE_ODDS
        self.min_score = min_score if min_score is not None else self.DEFAULT_MIN_SCORE
        self.max_score = max_score if max_score is not None else self.DEFAULT_MAX_SCORE
        self.min_prob = min_prob if min_prob is not None else self.DEFAULT_MIN_PROB
        self.max_prob = max_prob if max_prob is not None else self.DEFAULT_MAX_PROB

        # 参数校验
        self._validate_params()

        # 计算评分卡比例因子
        self.factor = self.pdo / log(2)
        self.offset = self.base_score - self.factor * log(self.base_odds)

    def _validate_params(self) -> None:
        """验证参数有效性"""
        if self.pdo <= 0:
            raise ValueError(f"pdo 必须大于 0，当前值: {self.pdo}")

        if self.base_odds <= 0:
            raise ValueError(f"base_odds 必须大于 0，当前值: {self.base_odds}")

        if self.min_score >= self.max_score:
            raise ValueError(
                f"min_score ({self.min_score}) 必须小于 max_score ({self.max_score})"
            )

        if self.min_prob <= 0:
            raise ValueError(f"min_prob 必须大于 0，当前值: {self.min_prob}")

        if self.max_prob >= 1:
            raise ValueError(f"max_prob 必须小于 1，当前值: {self.max_prob}")

        if self.min_prob >= self.max_prob:
            raise ValueError(
                f"min_prob ({self.min_prob}) 必须小于 max_prob ({self.max_prob})"
            )

    def _clip_prob(self, prob: float) -> float:
        """
        剪裁概率值到安全范围

        参数:
            prob: 原始概率

        返回:
            剪裁后的概率
        """
        if prob <= self.min_prob:
            return self.min_prob
        if prob >= self.max_prob:
            return self.max_prob
        return prob

    def to_score(self, prob: float) -> float:
        """
        将违约概率转换为信用分数

        参数:
            prob: 违约概率（0-1）

        返回:
            信用分数（浮点数）
        """
        # 边界处理，防止概率为0或1导致log异常
        prob = self._clip_prob(prob)

        odds = (1 - prob) / prob
        score = self.offset + self.factor * log(odds)

        # 分数边界裁剪
        score = max(score, self.min_score)
        score = min(score, self.max_score)

        return float(score)

    def to_score_batch(self, probs: List[float]) -> List[float]:
        """
        批量将违约概率转换为信用分数

        参数:
            probs: 违约概率列表

        返回:
            信用分数列表
        """
        return [self.to_score(p) for p in probs]

    def from_log_odds(self, log_odds: float) -> float:
        """
        将对数几率转换为信用分数

        参数:
            log_odds: 对数几率

        返回:
            信用分数
        """
        score = self.offset + self.factor * log_odds
        score = max(score, self.min_score)
        score = min(score, self.max_score)
        return float(score)

    def from_log_odds_batch(self, log_odds_list: List[float]) -> List[float]:
        """
        批量将对数几率转换为信用分数

        参数:
            log_odds_list: 对数几率列表

        返回:
            信用分数列表
        """
        return [self.from_log_odds(log_odds) for log_odds in log_odds_list]

    def to_probability(self, score: float) -> float:
        """
        将信用分数反向转换为违约概率

        参数:
            score: 信用分数

        返回:
            违约概率
        """
        # 从分数反推对数几率
        log_odds = (score - self.offset) / self.factor

        # 从对数几率反推概率
        prob = 1 / (1 + exp(-log_odds))

        # 剪裁到安全范围
        return self._clip_prob(prob)

    def to_probability_batch(self, scores: List[float]) -> List[float]:
        """
        批量将信用分数反向转换为违约概率

        参数:
            scores: 信用分数列表

        返回:
            违约概率列表
        """
        return [self.to_probability(score) for score in scores]

    def get_score_range(self) -> Tuple[float, float]:
        """
        获取有效分数范围

        返回:
            (min_score, max_score) 元组
        """
        return (self.min_score, self.max_score)

    def get_prob_range(self) -> Tuple[float, float]:
        """
        获取有效概率范围（剪裁阈值）

        返回:
            (min_prob, max_prob) 元组
        """
        return (self.min_prob, self.max_prob)

    def get_score_at_prob(self, prob: float) -> float:
        """
        获取指定概率对应的分数

        参数:
            prob: 违约概率

        返回:
            对应的信用分数
        """
        return self.to_score(prob)

    def get_prob_at_score(self, score: float) -> float:
        """
        获取指定分数对应的概率

        参数:
            score: 信用分数

        返回:
            对应的违约概率
        """
        return self.to_probability(score)

    def get_odds_at_score(self, score: float) -> float:
        """
        获取指定分数对应的 odds

        参数:
            score: 信用分数

        返回:
            odds 值
        """
        prob = self.to_probability(score)
        return (1 - prob) / prob

    def get_score_at_odds(self, odds: float) -> float:
        """
        获取指定 odds 对应的分数

        参数:
            odds: 好账/坏账比例

        返回:
            信用分数
        """
        prob = 1 / (1 + odds)
        return self.to_score(prob)

    def is_valid_score(self, score: float) -> bool:
        """
        检查分数是否在有效范围内

        参数:
            score: 信用分数

        返回:
            True 表示在范围内，False 表示不在
        """
        return self.min_score <= score <= self.max_score

    def is_valid_prob(self, prob: float) -> bool:
        """
        检查概率是否在有效范围内

        参数:
            prob: 违约概率

        返回:
            True 表示在范围内，False 表示不在
        """
        return self.min_prob <= prob <= self.max_prob

    def __repr__(self) -> str:
        return (
            f"Score(pdo={self.pdo}, base_score={self.base_score}, "
            f"base_odds={self.base_odds}, min_score={self.min_score}, "
            f"max_score={self.max_score}, min_prob={self.min_prob:.2e}, "
            f"max_prob={1 - self.max_prob:.2e})"
        )


# 便捷函数
def to_score(
    prob: float,
    pdo: float = 50,
    base_score: float = 600,
    base_odds: float = 20
) -> float:
    """
    将违约概率转换为信用分数（便捷函数）

    参数:
        prob: 违约概率
        pdo: 分数翻倍点，默认 50
        base_score: 基准分数，默认 600
        base_odds: 基准odds，默认 20

    返回:
        信用分数
    """
    scorer = Score(pdo=pdo, base_score=base_score, base_odds=base_odds)
    return scorer.to_score(prob)


def to_score_batch(
    probs: List[float],
    pdo: float = 50,
    base_score: float = 600,
    base_odds: float = 20
) -> List[float]:
    """
    批量将违约概率转换为信用分数（便捷函数）

    参数:
        probs: 违约概率列表
        pdo: 分数翻倍点，默认 50
        base_score: 基准分数，默认 600
        base_odds: 基准odds，默认 20

    返回:
        信用分数列表
    """
    scorer = Score(pdo=pdo, base_score=base_score, base_odds=base_odds)
    return scorer.to_score_batch(probs)


def to_probability(
    score: float,
    pdo: float = 50,
    base_score: float = 600,
    base_odds: float = 20
) -> float:
    """
    将信用分数反向转换为违约概率（便捷函数）

    参数:
        score: 信用分数
        pdo: 分数翻倍点，默认 50
        base_score: 基准分数，默认 600
        base_odds: 基准odds，默认 20

    返回:
        违约概率
    """
    scorer = Score(pdo=pdo, base_score=base_score, base_odds=base_odds)
    return scorer.to_probability(score)