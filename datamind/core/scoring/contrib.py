# datamind/core/scoring/contrib.py

"""特征贡献转换器

将 logit 空间的特征贡献转换为 score 空间，并提供排序和拆分功能。

核心功能：
  - logit_to_score: 单条 logit 贡献转 score 贡献
  - logit_to_score_batch: 批量 logit 贡献转 score 贡献
  - top_features: 获取 Top K 特征（用于 Reason Code）
  - top_features_by_impact: 分别获取正向和负向的 Top K 特征
  - split_positive_negative: 拆分正负贡献
  - contribution_summary: 获取贡献汇总统计

特性：
  - 解耦设计：不依赖 Explainer，只依赖 Score
  - 统一转换：factor × logit_contrib，与 Score 模块完全一致
  - 批量支持：支持单条和批量转换
  - 性能优化：预缓存 factor 和 offset
  - 容错处理：过滤 NaN/Inf 值
"""

from typing import Dict, List, Tuple
import numpy as np

from datamind.core.scoring.score import Score
from datamind.core.logging import get_logger

logger = get_logger(__name__)


class ContributionConverter:
    """特征贡献转换器

    将 logit 空间的贡献值转换为评分空间，并提供排序和拆分功能。

    核心公式：
        score_contribution = factor × logit_contribution

    其中 factor 是 Score 类的评分因子（pdo / ln(2)）。
    """

    def __init__(self, score: Score):
        """
        初始化转换器

        参数:
            score: Score 实例（包含 factor / offset）
        """
        self.score = score

        # 提前缓存，提高性能
        self.factor = score.factor
        self.offset = score.offset

        logger.debug(
            "ContributionConverter 初始化: factor=%.6f, offset=%.6f",
            self.factor,
            self.offset
        )

    # ==================== 核心转换 ====================

    def logit_to_score(self, contribution: Dict[str, float]) -> Dict[str, float]:
        """
        将 logit 贡献转换为 score 贡献

        参数:
            contribution: 特征对 logit 的贡献字典，格式 {"feature_name": logit_contribution}

        返回:
            特征对评分的贡献字典，格式 {"feature_name": score_contribution}
        """
        if not contribution:
            return {}

        result = {}

        for k, v in contribution.items():
            try:
                if np.isfinite(v):
                    result[k] = float(self.factor * v)
            except Exception as e:
                logger.debug("转换特征 %s 失败: %s", k, e)
                continue

        return result

    def logit_to_score_batch(
        self,
        contributions: List[Dict[str, float]]
    ) -> List[Dict[str, float]]:
        """
        批量将 logit 贡献转换为 score 贡献

        参数:
            contributions: logit 贡献字典列表

        返回:
            score 贡献字典列表
        """
        if not contributions:
            return []

        return [self.logit_to_score(c) for c in contributions]

    def score_to_logit(self, contribution: Dict[str, float]) -> Dict[str, float]:
        """
        将 score 贡献转换为 logit 贡献（反向转换）

        参数:
            contribution: 特征对评分的贡献字典

        返回:
            特征对 logit 的贡献字典
        """
        if not contribution:
            return {}

        result = {}

        for k, v in contribution.items():
            try:
                if np.isfinite(v):
                    result[k] = float(v / self.factor)
            except Exception as e:
                logger.debug("反向转换特征 %s 失败: %s", k, e)
                continue

        return result

    def score_to_logit_batch(
        self,
        contributions: List[Dict[str, float]]
    ) -> List[Dict[str, float]]:
        """
        批量将 score 贡献转换为 logit 贡献

        参数:
            contributions: score 贡献字典列表

        返回:
            logit 贡献字典列表
        """
        if not contributions:
            return []

        return [self.score_to_logit(c) for c in contributions]

    # ==================== 排序 / Reason Code ====================

    @staticmethod
    def top_features(
        contribution: Dict[str, float],
        top_k: int = 5,
        reverse: bool = True
    ) -> List[Tuple[str, float]]:
        """
        获取 Top K 特征（用于 Reason Code）

        参数:
            contribution: 贡献字典（可以是 logit 或 score 空间，建议用 score）
            top_k: 返回前 K 个特征
            reverse: True 表示按绝对值降序（影响最大优先），False 表示升序

        返回:
            特征名和贡献值的元组列表，格式 [(feature, contribution), ...]
        """
        if not contribution:
            return []

        items = sorted(
            contribution.items(),
            key=lambda x: abs(x[1]),
            reverse=reverse
        )

        return items[:top_k]

    @staticmethod
    def top_features_by_impact(
        contribution: Dict[str, float],
        top_k: int = 5
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        分别获取正向和负向的 Top K 特征

        参数:
            contribution: 贡献字典（建议用 score 空间）
            top_k: 每类返回前 K 个

        返回:
            {
                "positive": [(feature, contribution), ...],
                "negative": [(feature, contribution), ...]
            }
        """
        if not contribution:
            return {"positive": [], "negative": []}

        positive = [(k, v) for k, v in contribution.items() if v > 0]
        negative = [(k, v) for k, v in contribution.items() if v < 0]

        positive_sorted = sorted(positive, key=lambda x: x[1], reverse=True)[:top_k]
        negative_sorted = sorted(negative, key=lambda x: abs(x[1]), reverse=True)[:top_k]

        return {
            "positive": positive_sorted,
            "negative": negative_sorted
        }

    @staticmethod
    def split_positive_negative(
        contribution: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """
        拆分正负贡献（用于风控解释）

        参数:
            contribution: 贡献字典（建议用 score 空间）

        返回:
            {
                "positive": {"feature": contribution, ...},
                "negative": {"feature": contribution, ...}
            }
        """
        positive = {}
        negative = {}

        for k, v in contribution.items():
            if v > 0:
                positive[k] = v
            elif v < 0:
                negative[k] = v

        return {
            "positive": positive,
            "negative": negative
        }

    # ==================== 统计汇总 ====================

    @staticmethod
    def total_contribution(contribution: Dict[str, float]) -> float:
        """
        计算总贡献（验证用）

        对于 score 空间的贡献，总和应等于 final_score - offset

        参数:
            contribution: 贡献字典

        返回:
            总贡献值
        """
        return sum(contribution.values())

    @staticmethod
    def contribution_summary(contribution: Dict[str, float]) -> Dict[str, float]:
        """
        获取贡献汇总统计

        参数:
            contribution: 贡献字典

        返回:
            {
                "total": 总贡献,
                "positive_sum": 正向贡献总和,
                "negative_sum": 负向贡献总和,
                "max_positive": 最大正向贡献,
                "max_negative": 最大负向贡献（绝对值）
            }
        """
        if not contribution:
            return {
                "total": 0.0,
                "positive_sum": 0.0,
                "negative_sum": 0.0,
                "max_positive": 0.0,
                "max_negative": 0.0
            }

        values = list(contribution.values())
        positive_sum = sum(v for v in values if v > 0)
        negative_sum = sum(v for v in values if v < 0)

        return {
            "total": sum(values),
            "positive_sum": positive_sum,
            "negative_sum": negative_sum,
            "max_positive": max(values) if values else 0.0,
            "max_negative": min(values) if values else 0.0
        }

    # ==================== 辅助方法 ====================

    def get_factor(self) -> float:
        """获取评分因子 B"""
        return self.factor

    def get_offset(self) -> float:
        """获取评分偏移 A"""
        return self.offset

    def __repr__(self) -> str:
        return (
            f"ContributionConverter(factor={self.factor:.6f}, offset={self.offset:.6f})"
        )


# ==================== 便捷函数 ====================

def logit_to_score(
    contribution: Dict[str, float],
    pdo: float = 50,
    base_score: float = 600,
    base_odds: float = 20
) -> Dict[str, float]:
    """
    将 logit 贡献转换为 score 贡献（便捷函数）

    参数:
        contribution: logit 贡献字典
        pdo: 分数翻倍点
        base_score: 基准分数
        base_odds: 基准 odds

    返回:
        score 贡献字典
    """
    from datamind.core.scoring.score import Score

    score = Score(pdo=pdo, base_score=base_score, base_odds=base_odds)
    converter = ContributionConverter(score)
    return converter.logit_to_score(contribution)


def top_features(
    contribution: Dict[str, float],
    top_k: int = 5
) -> List[Tuple[str, float]]:
    """
    获取 Top K 特征（便捷函数）

    参数:
        contribution: 贡献字典（score 空间）
        top_k: 返回前 K 个

    返回:
        特征名和贡献值的元组列表
    """
    if not contribution:
        return []

    items = sorted(
        contribution.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )

    return items[:top_k]