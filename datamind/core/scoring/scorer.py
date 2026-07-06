# datamind/core/scoring/scorer.py

"""评分器

基于模型预测结果计算评分。

核心功能：
    - score: 单条评分
    - probability_to_score: 概率转评分
    - logit_to_score: Logit 转评分

使用示例：
    from datamind.core.inference import Inference
    from datamind.core.scoring.scorer import Scorer

    inference = Inference(
        model=model,
        feature_names=feature_names,
        data_types=data_types,
    )

    scorer = Scorer(inference)

    score = scorer.score(features)
"""

from typing import Any

import structlog

from datamind.core.inference import Inference
from datamind.core.scoring.transformer import ScoreTransformer

logger = structlog.get_logger(__name__)


class Scorer:
    """评分器

    基于模型 Logit 输出计算评分。

    属性：
        inference: 推理器
        transformer: 评分转换器
    """

    def __init__(
            self,
            inference: Inference,
            transformer: ScoreTransformer | None = None,
    ):
        """初始化评分器

        参数：
            inference: 推理器
            transformer: 评分转换器，为 None 时使用默认配置
        """
        self.inference = inference
        self.transformer = transformer or ScoreTransformer()

        logger.debug(
            "初始化评分器 | transformer=%s",
            self.transformer.__class__.__name__,
        )

    def score(self, X: Any) -> float:
        """计算评分

        参数：
            X: 输入数据，支持单条字典或字典列表

        返回：
            float: 评分
        """
        logit = self.inference.predict_logit(X)

        score = self.transformer.logit_to_score(logit)

        logger.debug(
            "评分完成 | score=%s",
            score,
        )

        return score

    def probability_to_score(self, probability: float) -> float:
        """违约概率转评分

        参数：
            probability: 违约概率，取值范围 (0, 1)

        返回：
            float: 评分
        """
        score = self.transformer.probability_to_score(probability)

        logger.debug(
            "概率转评分 | probability=%s | score=%s",
            probability,
            score,
        )

        return score

    def logit_to_score(self, logit: float) -> float:
        """Logit 转评分

        参数：
            logit: Logit 值

        返回：
            float: 评分
        """
        score = self.transformer.logit_to_score(logit)

        logger.debug(
            "logit 转评分 | logit=%s | score=%s",
            logit,
            score,
        )

        return score
