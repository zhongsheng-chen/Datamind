# datamind/core/scoring/transformer.py

"""评分转换器

负责违约概率、Logit 与评分之间的双向转换。

核心功能：
  - probability_to_score: 违约概率转评分
  - score_to_probability: 评分转违约概率
  - logit_to_score: Logit 转评分
  - score_to_logit: 评分转 Logit
  - probability_to_logit: 违约概率转 Logit
  - logit_to_probability: Logit 转违约概率

注意：
  - probability 表示违约概率。
  - Logit 表示违约概率对应的对数几率：

      logit = ln(probability / (1 - probability))

  - base_odds 表示基准好坏比，即正常概率与违约概率之比。
  - 违约概率越高，Logit 越大，评分越低。
  - logit_to_score 会将评分限制在 min_score 和 max_score 之间。

使用示例：
  from datamind.core.scoring.transformer import ScoreTransformer

  transformer = ScoreTransformer()

  score = transformer.probability_to_score(
      probability=0.3
  )

  probability = transformer.score_to_probability(
      score=650
  )

  score = transformer.logit_to_score(
      logit=1.2
  )
"""

import math

import structlog

from datamind.config.scorecard import ScorecardConfig

logger = structlog.get_logger(__name__)


class ScoreTransformer:
    """评分转换器

    属性：
        config: 评分卡配置
        factor: 评分因子，等于 PDO / ln(2)
        offset: 评分偏移，等于
            base_score - factor * ln(base_odds)
    """

    def __init__(
            self,
            config: ScorecardConfig | None = None,
    ) -> None:
        """初始化评分转换器

        参数：
            config: 评分卡配置，为 None 时使用默认配置
        """
        self.config = (
            config
            if config is not None
            else ScorecardConfig()
        )

        self.factor: float = (
            self.config.pdo
            / math.log(2)
        )

        self.offset: float = (
            self.config.base_score
            - self.factor
            * math.log(
                self.config.base_odds
            )
        )

        logger.debug(
            "初始化评分转换器",
            base_score=self.config.base_score,
            base_odds=self.config.base_odds,
            pdo=self.config.pdo,
            factor=self.factor,
            offset=self.offset,
        )

    def probability_to_score(
            self,
            probability: float,
    ) -> float:
        """违约概率转评分

        参数：
            probability: 违约概率，取值范围 (0, 1)

        返回：
            限制在 min_score 和 max_score
            之间的评分值

        异常：
            ValueError: probability 不是有限数值
                或不在 (0, 1) 区间内
        """
        logit = self.probability_to_logit(
            probability
        )

        return self.logit_to_score(
            logit
        )

    def score_to_probability(
            self,
            score: float,
    ) -> float:
        """评分转违约概率

        参数：
            score: 评分值

        返回：
            违约概率，取值范围 [0, 1]

        异常：
            ValueError: score 不是有限数值
        """
        logit = self.score_to_logit(
            score
        )

        return self.logit_to_probability(
            logit
        )

    def logit_to_score(
            self,
            logit: float,
    ) -> float:
        """Logit 转评分

        参数：
            logit: 违约概率对应的 Logit

        返回：
            限制在 min_score 和 max_score
            之间的评分值

        异常：
            ValueError: logit 不是有限数值
        """
        logit_value = self._require_finite(
            logit,
            name="logit",
        )

        score = (
            self.offset
            - self.factor * logit_value
        )

        result = self._clamp_score(
            score
        )

        logger.debug(
            "Logit 转评分",
            logit=logit_value,
            score=result,
        )

        return result

    def score_to_logit(
            self,
            score: float,
    ) -> float:
        """评分转 Logit

        参数：
            score: 评分值

        返回：
            违约概率对应的 Logit

        异常：
            ValueError: score 不是有限数值
        """
        score_value = self._require_finite(
            score,
            name="score",
        )

        result = (
            self.offset - score_value
        ) / self.factor

        logger.debug(
            "评分转 Logit",
            score=score_value,
            logit=result,
        )

        return result

    @staticmethod
    def probability_to_logit(
            probability: float,
    ) -> float:
        """违约概率转 Logit

        参数：
            probability: 违约概率，取值范围 (0, 1)

        返回：
            ln(probability / (1 - probability))

        异常：
            ValueError: probability 不是有限数值
                或不在 (0, 1) 区间内
        """
        probability_value = (
            ScoreTransformer._require_finite(
                probability,
                name="probability",
            )
        )

        if not 0 < probability_value < 1:
            raise ValueError(
                "probability 必须在 (0, 1) 区间内"
            )

        result = (
            math.log(
                probability_value
            )
            - math.log1p(
                -probability_value
            )
        )

        logger.debug(
            "违约概率转 Logit",
            probability=probability_value,
            logit=result,
        )

        return result

    @staticmethod
    def logit_to_probability(
            logit: float,
    ) -> float:
        """Logit 转违约概率

        使用数值稳定的 Sigmoid 计算方式，
        避免极端 Logit 导致指数溢出。

        参数：
            logit: 违约概率对应的 Logit

        返回：
            违约概率，取值范围 [0, 1]

        异常：
            ValueError: logit 不是有限数值
        """
        logit_value = (
            ScoreTransformer._require_finite(
                logit,
                name="logit",
            )
        )

        if logit_value >= 0:
            exp_value = math.exp(
                -logit_value
            )

            result = 1 / (
                1 + exp_value
            )

        else:
            exp_value = math.exp(
                logit_value
            )

            result = exp_value / (
                1 + exp_value
            )

        logger.debug(
            "Logit 转违约概率",
            logit=logit_value,
            probability=result,
        )

        return result

    def _clamp_score(
            self,
            score: float,
    ) -> float:
        """将评分限制在配置范围内"""
        return max(
            self.config.min_score,
            min(
                self.config.max_score,
                score,
            ),
        )

    @staticmethod
    def _require_finite(
            value: float,
            *,
            name: str,
    ) -> float:
        """校验并返回有限浮点数

        参数：
            value: 原始数值
            name: 参数名称

        返回：
            浮点数值

        异常：
            ValueError: 数值不是有限值
        """
        try:
            numeric_value = float(
                value
            )
        except (
                TypeError,
                ValueError,
        ) as exc:
            raise ValueError(
                f"{name} 必须是数值"
            ) from exc

        if not math.isfinite(
                numeric_value
        ):
            raise ValueError(
                f"{name} 必须是有限数值"
            )

        return numeric_value
