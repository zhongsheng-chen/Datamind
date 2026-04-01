# datamind/core/scoring/score.py

"""信用评分转换器

将逻辑回归输出（logit）转换为信用评分。

核心公式：
    score = offset - factor × logit
    factor = pdo / ln(2)
    offset = base_score - factor × ln(base_odds)

空间定义：
    prob: 违约概率空间，值域 [0,1]
    logit: 逻辑回归输出空间，值域 (-∞, +∞)，公式 logit = log(p/(1-p))
    score: 信用评分空间，值域 [min_score, max_score]

设计原则：
    所有转换最终统一到 logit 空间，logit 是系统的唯一核心物理量。
    概率空间通过 _logit_from_prob / _sigmoid 与 logit 空间互转。
    评分空间通过 from_logit / to_logit 与 logit 空间互转。

核心功能：
    - from_logit: 逻辑回归输出转信用评分
    - to_score: 违约概率转信用评分
    - to_probability: 信用评分转违约概率
    - from_logit_batch: 批量逻辑回归输出转信用评分
    - to_score_batch: 批量违约概率转信用评分
    - to_probability_batch: 批量信用评分转违约概率
    - get_score_at_odds: 获取指定 odds 对应的评分
    - get_odds_at_score: 获取指定评分对应的 odds

特性：
    - 统一 logit 核心：所有路径最终调用 from_logit，确保公式唯一
    - 数值稳定：使用稳定版 sigmoid，防止 exp 溢出
    - 边界控制：支持评分边界裁剪和概率剪裁
    - 参数校验：自动验证单调性和 PDO 正确性
    - 批量优化：NumPy 向量化实现，性能提升 10~100 倍
"""

from typing import List
from math import log, exp
import numpy as np

from datamind.core.logging.manager import LogManager

_log_manager = LogManager()
logger = _log_manager.app_logger


class Score:
    """信用评分转换器

    以 logit 空间为核心，提供 prob、logit、score 三空间互转。
    所有路径最终统一到 logit，确保公式唯一、易于维护。
    """

    def __init__(
        self,
        pdo: float = 50.0,
        base_score: float = 600.0,
        base_odds: float = 20.0,
        min_score: float = 0.0,
        max_score: float = 1000.0,
        min_prob: float = 1e-6,
        max_prob: float = 1 - 1e-6,
        validate: bool = True
    ):
        """
        初始化信用评分转换器

        参数:
            pdo: 分数翻倍点
            base_score: 基准分数
            base_odds: 基准 odds（好/坏比例）
            min_score: 最低分数限制
            max_score: 最高分数限制
            min_prob: 概率最小值剪裁阈值
            max_prob: 概率最大值剪裁阈值
            validate: 是否执行参数校验
        """
        if validate:
            self._validate_params(pdo, base_odds, min_score, max_score, min_prob, max_prob)

        self.pdo = pdo
        self.base_score = base_score
        self.base_odds = base_odds
        self.min_score = min_score
        self.max_score = max_score
        self.min_prob = min_prob
        self.max_prob = max_prob

        # 计算转换因子
        self.factor = pdo / log(2)
        self.offset = base_score - self.factor * log(base_odds)

        if validate:
            self._validate_monotonicity()
            self._validate_pdo()

        logger.debug(
            "信用评分转换器初始化完成: pdo=%.2f, base_score=%.2f, base_odds=%.2f, "
            "score_range=[%.2f, %.2f], prob_range=[%.2e, %.2e]",
            pdo, base_score, base_odds, min_score, max_score, min_prob, max_prob
        )

    # ==================== 参数校验 ====================

    @staticmethod
    def _validate_params(pdo, base_odds, min_score, max_score, min_prob, max_prob):
        """验证参数有效性"""
        if pdo <= 0:
            raise ValueError(f"pdo 必须大于 0，当前值: {pdo}")
        if base_odds <= 0:
            raise ValueError(f"base_odds 必须大于 0，当前值: {base_odds}")
        if min_score >= max_score:
            raise ValueError(f"min_score ({min_score}) 必须小于 max_score ({max_score})")
        if min_prob <= 0:
            raise ValueError(f"min_prob 必须大于 0，当前值: {min_prob}")
        if max_prob >= 1:
            raise ValueError(f"max_prob 必须小于 1，当前值: {max_prob}")
        if min_prob >= max_prob:
            raise ValueError(f"min_prob ({min_prob}) 必须小于 max_prob ({max_prob})")

    def _validate_monotonicity(self):
        """验证分数单调性：违约概率越高，信用分数越低"""
        p_low = self.min_prob + (self.max_prob - self.min_prob) * 0.1
        p_high = self.min_prob + (self.max_prob - self.min_prob) * 0.9
        score_low = self.to_score(p_low)
        score_high = self.to_score(p_high)

        if p_low < p_high and score_low <= score_high:
            error_msg = (
                f"分数单调性校验失败: 违约概率 {p_low:.6f} 对应分数 {score_low:.2f}, "
                f"违约概率 {p_high:.6f} 对应分数 {score_high:.2f}。"
                f"分数应随违约概率增加而降低，请检查参数配置。"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _validate_pdo(self):
        """验证 PDO 正确性：odds 翻倍时，分数增加 pdo 分"""
        odds = self.base_odds
        score1 = self._score_at_odds(odds)
        score2 = self._score_at_odds(odds * 2)

        if abs(score2 - score1 - self.pdo) > 1e-6:
            error_msg = (
                f"PDO 校验失败: odds={odds} 分数={score1:.2f}, "
                f"odds={odds*2} 分数={score2:.2f}, "
                f"期望差值={self.pdo:.2f}, 实际差值={score2 - score1:.2f}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    # ==================== 内部裁剪方法 ====================

    def _clip_prob(self, prob: float) -> float:
        """剪裁概率到安全范围"""
        if prob <= self.min_prob:
            return self.min_prob
        if prob >= self.max_prob:
            return self.max_prob
        return prob

    def _clip_score(self, score: float) -> float:
        """剪裁分数到有效范围"""
        if score <= self.min_score:
            return self.min_score
        if score >= self.max_score:
            return self.max_score
        return score

    def _score_at_odds(self, odds: float) -> float:
        """直接通过 odds 计算分数，避免多次转换"""
        score = self.offset + self.factor * log(odds)
        return self._clip_score(score)

    # ==================== 数值稳定的 sigmoid / logit ====================

    @staticmethod
    def _sigmoid(x: float) -> float:
        """数值稳定的 sigmoid 函数"""
        if x >= 0:
            return 1 / (1 + exp(-x))
        else:
            z = exp(x)
            return z / (1 + z)

    @staticmethod
    def _sigmoid_np(x: np.ndarray) -> np.ndarray:
        """数值稳定的 sigmoid 函数（NumPy 向量化）"""
        return np.where(
            x >= 0,
            1 / (1 + np.exp(-x)),
            np.exp(x) / (1 + np.exp(x))
        )

    @staticmethod
    def _logit_from_prob(prob: float) -> float:
        """概率转 logit（内部使用，不做剪裁）"""
        return log(prob / (1 - prob))

    @staticmethod
    def _logit_from_prob_np(probs: np.ndarray) -> np.ndarray:
        """概率数组转 logit 数组（内部使用，不做剪裁）"""
        return np.log(probs / (1 - probs))

    # ==================== 核心 API ====================

    def from_logit(self, logit: float) -> float:
        """
        逻辑回归输出（logit）转信用分数

        核心公式: score = offset - factor × logit

        参数:
            logit: 逻辑回归输出，即 log(p/(1-p))

        返回:
            信用分数
        """
        score = self.offset - self.factor * logit
        result = self._clip_score(score)
        logger.debug("logit转分数: logit=%.6f -> score=%.2f", logit, result)
        return result

    def from_logit_batch(self, logits: List[float]) -> List[float]:
        """
        批量将逻辑回归输出转换为信用分数

        参数:
            logits: 逻辑回归输出列表

        返回:
            信用分数列表
        """
        return self.from_logit_batch_np(np.array(logits)).tolist()

    def from_logit_batch_np(self, logits: np.ndarray) -> np.ndarray:
        """
        批量将逻辑回归输出转换为信用分数（NumPy 向量化）

        参数:
            logits: 逻辑回归输出数组

        返回:
            信用分数数组
        """
        scores = self.offset - self.factor * logits
        return np.clip(scores, self.min_score, self.max_score)

    def to_logit(self, score: float) -> float:
        """
        信用分数转逻辑回归输出（logit）

        公式: logit = (offset - score) / factor

        参数:
            score: 信用分数

        返回:
            逻辑回归输出
        """
        return (self.offset - score) / self.factor

    def to_score(self, prob: float) -> float:
        """
        违约概率转信用分数

        统一路径: prob → logit → score

        参数:
            prob: 违约概率 (0-1)

        返回:
            信用分数
        """
        prob = self._clip_prob(prob)
        logit = self._logit_from_prob(prob)
        return self.from_logit(logit)

    def to_score_batch(self, probs: List[float]) -> List[float]:
        """
        批量将违约概率转换为信用分数

        参数:
            probs: 违约概率列表

        返回:
            信用分数列表
        """
        return self.to_score_batch_np(np.array(probs)).tolist()

    def to_score_batch_np(self, probs: np.ndarray) -> np.ndarray:
        """
        批量将违约概率转换为信用分数（NumPy 向量化）

        统一路径: prob → logit → score

        参数:
            probs: 违约概率数组

        返回:
            信用分数数组
        """
        probs = np.clip(probs, self.min_prob, self.max_prob)
        logits = self._logit_from_prob_np(probs)
        return self.from_logit_batch_np(logits)

    def to_probability(self, score: float) -> float:
        """
        信用分数转违约概率

        统一路径: score → logit → prob

        参数:
            score: 信用分数

        返回:
            违约概率
        """
        logit = self.to_logit(score)
        prob = self._sigmoid(logit)
        result = self._clip_prob(prob)
        logger.debug("分数转概率: score=%.2f -> prob=%.6f", score, result)
        return result

    def to_probability_batch(self, scores: List[float]) -> List[float]:
        """
        批量将信用分数转换为违约概率

        参数:
            scores: 信用分数列表

        返回:
            违约概率列表
        """
        return self.to_probability_batch_np(np.array(scores)).tolist()

    def to_probability_batch_np(self, scores: np.ndarray) -> np.ndarray:
        """
        批量将信用分数转换为违约概率（NumPy 向量化）

        统一路径: score → logit → prob

        参数:
            scores: 信用分数数组

        返回:
            违约概率数组
        """
        logits = (self.offset - scores) / self.factor
        probs = self._sigmoid_np(logits)
        return np.clip(probs, self.min_prob, self.max_prob)

    # ==================== odds 相关方法 ====================

    def get_score_at_odds(self, odds: float) -> float:
        """
        获取指定 odds 对应的信用分数

        odds 定义: odds = (1-p)/p，好/坏比例

        参数:
            odds: 好/坏比例

        返回:
            信用分数
        """
        return self._score_at_odds(odds)

    def get_odds_at_score(self, score: float) -> float:
        """
        获取指定信用分数对应的 odds

        参数:
            score: 信用分数

        返回:
            odds 值（好/坏比例）
        """
        score = self._clip_score(score)
        return exp((score - self.offset) / self.factor)

    # ==================== 辅助方法 ====================

    def get_factor(self) -> float:
        """获取评分因子 B"""
        return self.factor

    def get_offset(self) -> float:
        """获取评分偏移 A"""
        return self.offset

    def get_pdo(self) -> float:
        """获取 PDO 值"""
        return self.pdo

    def get_base_odds(self) -> float:
        """获取基准 odds"""
        return self.base_odds

    def get_base_logit(self) -> float:
        """获取基准 logit 值"""
        return -log(self.base_odds)

    def get_score_range(self) -> tuple:
        """获取有效分数范围"""
        return (self.min_score, self.max_score)

    def get_prob_range(self) -> tuple:
        """获取有效概率范围"""
        return (self.min_prob, self.max_prob)

    def __repr__(self) -> str:
        return (
            f"Score(pdo={self.pdo}, base_score={self.base_score}, "
            f"base_odds={self.base_odds}, score_range=[{self.min_score}, {self.max_score}])"
        )


# ==================== 便捷函数 ====================

def to_score(
    prob: float,
    pdo: float = 50,
    base_score: float = 600,
    base_odds: float = 20,
    min_score: float = 0,
    max_score: float = 1000
) -> float:
    """违约概率转信用分数"""
    scorer = Score(pdo=pdo, base_score=base_score, base_odds=base_odds,
                   min_score=min_score, max_score=max_score)
    return scorer.to_score(prob)


def from_logit(
    logit: float,
    pdo: float = 50,
    base_score: float = 600,
    base_odds: float = 20,
    min_score: float = 0,
    max_score: float = 1000
) -> float:
    """逻辑回归输出转信用分数"""
    scorer = Score(pdo=pdo, base_score=base_score, base_odds=base_odds,
                   min_score=min_score, max_score=max_score)
    return scorer.from_logit(logit)


def to_probability(
    score: float,
    pdo: float = 50,
    base_score: float = 600,
    base_odds: float = 20,
    min_prob: float = 1e-6,
    max_prob: float = 1 - 1e-6
) -> float:
    """信用分数转违约概率"""
    scorer = Score(pdo=pdo, base_score=base_score, base_odds=base_odds,
                   min_prob=min_prob, max_prob=max_prob)
    return scorer.to_probability(score)