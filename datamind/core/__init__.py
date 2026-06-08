# datamind/core/__init__.py

"""核心模块

提供 Datamind 的核心功能，包括模型适配、推理和评分。

核心功能：
    - model.adapters: 模型适配器，支持多种机器学习框架
    - inference: 统一推理接口
    - scoring: 评分卡相关功能

使用示例：
    from datamind.core import Inference, Scorer, ScoreTransformer

    # 创建推理实例
    inference = Inference(
        model=model,
        feature_names=["age", "income", "credit_score"],
        data_types={"age": "numerical", "income": "numerical"},
    )

    # 预测概率
    prob = inference.predict({"age": 30, "income": 50000})

    # 创建评分器
    scorer = Scorer(inference)
    score = scorer.score({"age": 30, "income": 50000})
"""

from datamind.core.inference import Inference
from datamind.core.scoring import Scorer, ScoreTransformer, LRContrib
from datamind.core.scoring.base import BaseScorer
from datamind.core.capability import ModelCapability, ScorecardCapability

__all__ = [
    "Inference",
    "BaseScorer",
    "LRContrib",
    "Scorer",
    "ScoreTransformer",
    "ModelCapability",
    "ScorecardCapability",
]