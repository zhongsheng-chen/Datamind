# datamind/core/scoring/transformer.py

"""评分转换器

负责 Logit、Odds、Probability 与 Score 的转换。

核心功能：
    - logit_to_score: Logit 转评分
    - score_to_logit: 评分转 Logit
    - probability_to_score: 违约概率转评分
    - score_to_probability: 评分转违约概率
    - probability_to_logit: 违约概率转 Logit
    - logit_to_probability: Logit 转违约概率

使用示例：
    from datamind.core.scoring.transformer import ScoreTransformer

    # 创建评分转换器
    transformer = ScoreTransformer()

    # 概率转评分
    score = transformer.probability_to_score(probability=0.3)

    # 评分转概率
    prob = transformer.score_to_probability(score=650)

    # Logit 转评分
    score = transformer.logit_to_score(logit=1.2)
"""

import math

import structlog

from datamind.config.scorecard import ScorecardConfig

logger = structlog.get_logger(__name__)


class ScoreTransformer:
    """评分转换器

    属性：
        config: 评分卡配置
        factor: 因子值 = PDO / ln(2)
        offset: 偏移量 = base_score + factor * ln(base_odds)
    """

    def __init__(
            self,
            config: ScorecardConfig | None = None,
    ):
        """初始化评分转换器

        参数：
            config: 评分卡配置，为 None 时使用默认配置
        """
        self.config = config or ScorecardConfig()

        self.factor = self.config.pdo / math.log(2)
        self.offset = self.config.base_score + self.factor * math.log(self.config.base_odds)

        logger.debug(
            "初始化评分转换器 | base_score=%s | base_odds=%s | pdo=%s | factor=%s | offset=%s",
            self.config.base_score,
            self.config.base_odds,
            self.config.pdo,
            self.factor,
            self.offset,
        )

    def logit_to_score(self, logit: float) -> float:
        """Logit 转评分

        参数：
            logit: Logit 值

        返回：
            float: 评分值（限制在 min_score 和 max_score 之间）
        """
        logger.debug("logit 转评分 | logit=%s", logit)

        score = self.offset - self.factor * float(logit)

        return max(
            self.config.min_score,
            min(self.config.max_score, score),
        )

    def score_to_logit(self, score: float) -> float:
        """评分转 Logit

        参数：
            score: 评分值

        返回：
            float: Logit 值
        """
        logger.debug("评分转 logit | score=%s", score)

        return (self.offset - float(score)) / self.factor

    def probability_to_score(self, probability: float) -> float:
        """违约概率转评分

        参数：
            probability: 违约概率，取值范围 (0, 1)

        返回：
            float: 评分值

        异常：
            ValueError: probability 不在 (0,1) 区间内
        """
        logger.debug("概率转评分 | probability=%s", probability)

        if not 0 < probability < 1:
            raise ValueError("probability 必须在 (0,1) 区间内")

        odds = (1 - probability) / probability
        logit = math.log(odds)

        return self.logit_to_score(logit)

    def score_to_probability(self, score: float) -> float:
        """评分转违约概率

        参数：
            score: 评分值

        返回：
            float: 违约概率，取值范围 (0, 1)
        """
        logger.debug("评分转概率 | score=%s", score)

        logit = self.score_to_logit(score)
        odds = math.exp(logit)

        return 1 / (1 + odds)

    @staticmethod
    def probability_to_logit(probability: float) -> float:
        """违约概率转 Logit

        参数：
            probability: 违约概率，取值范围 (0, 1)

        返回：
            float: Logit 值

        异常：
            ValueError: probability 不在 (0,1) 区间内
        """
        logger.debug("概率转 logit | probability=%s", probability)

        if not 0 < probability < 1:
            raise ValueError("probability 必须在 (0,1) 区间内")

        odds = (1 - probability) / probability

        return math.log(odds)

    @staticmethod
    def logit_to_probability(logit: float) -> float:
        """Logit 转违约概率

        参数：
            logit: Logit 值

        返回：
            float: 违约概率，取值范围 (0, 1)
        """
        logger.debug("logit 转概率 | logit=%s", logit)

        odds = math.exp(float(logit))

        return 1 / (1 + odds)
