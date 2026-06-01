# datamind/core/scoring/contrib.py

"""特征贡献分解器

仅支持 Logistic Regression 模型。

核心功能：
    - explain: 特征贡献分解
    - explain_batch: 批量特征贡献分解

说明：
    Logistic Regression 在线性空间中的表达为：

        logit = Σ(w_i * x_i) + b

    通过 PDO（Points to Double Odds）刻度映射到评分空间：

        score = offset - factor * logit

    展开后得到可加性分解形式：

        score = intercept_score + Σ feature_score_i

    其中各部分定义为：

        intercept_score = offset - factor * b
        feature_score_i = -factor * w_i * x_i

使用示例：
    from datamind.core.inference import Inference
    from datamind.core.scoring.contrib import LRContrib

    inference = Inference(model=model, feature_names=feature_names)
    contrib = LRContrib(inference)

    # 特征贡献分解
    result = contrib.explain({"age": 30, "income": 50000})

    # 批量特征贡献分解
    results = contrib.explain_batch([
        {"age": 30, "income": 50000},
        {"age": 40, "income": 80000},
    ])
"""

import structlog
import numpy as np

from typing import Any

from datamind.core.inference import Inference
from datamind.core.scoring.transformer import ScoreTransformer

logger = structlog.get_logger(__name__)


class LRContrib:
    """逻辑回归特征贡献分解器

    属性：
        inference: 推理器
        transformer: 评分转换器
        coef: 模型系数
        intercept: 模型截距
        factor: 评分因子
        offset: 评分偏移
    """

    def __init__(
        self,
        inference: Inference,
        transformer: ScoreTransformer | None = None,
    ):
        """初始化逻辑回归特征贡献分解器

        参数：
            inference: 推理器
            transformer: 评分转换器，为 None 时使用默认配置

        异常：
            NotImplementedError: 模型不具有 coef_ 属性
        """
        self.inference = inference
        self.transformer = transformer or ScoreTransformer()

        model = inference.adapter.model

        if not hasattr(model, "coef_"):
            raise NotImplementedError("LRContrib 仅支持具有 coef_ 的线性模型")

        self.coef = np.asarray(model.coef_).reshape(-1)

        self.intercept = float(getattr(model, "intercept_", 0.0))

        self.factor = self.transformer.factor
        self.offset = self.transformer.offset

        logger.debug(
            "初始化逻辑回归特征贡献分解器 | 特征数=%d",
            len(self.coef),
        )

    def _explain_one(self, x: np.ndarray) -> dict[str, float]:
        """单样本特征贡献分解（内部方法）

        参数：
            x: 输入特征数组，形状为 (n_features,)

        返回：
            dict[str, float]: 评分拆解结果，包含 intercept_score、feature_score、total_score 和各特征贡献
        """
        contributions: dict[str, float] = {}
        feature_score: float = 0.0

        feature_names = self.inference.adapter.feature_names

        for i, (xi, wi) in enumerate(zip(x, self.coef)):
            xi_val = (
                0.0
                if xi is None or (isinstance(xi, float) and np.isnan(xi))
                else float(xi)
            )

            contrib_score = -self.factor * float(wi) * xi_val

            if feature_names and i < len(feature_names):
                feature_key = feature_names[i]
            else:
                feature_key = f"特征{i}"

            contributions[feature_key] = contrib_score
            feature_score += contrib_score

        intercept_score = self.offset - self.factor * self.intercept

        total_score = intercept_score + feature_score

        return {
            "intercept_score": intercept_score,
            "feature_score": feature_score,
            "total_score": total_score,
            **contributions,
        }

    def explain(self, X: Any) -> dict[str, float]:
        """单样本特征贡献分解

        参数：
            X: 输入数据，支持单条字典或 numpy 数组

        返回：
            dict[str, float]: 评分拆解结果
        """
        x = self.inference.transform(X)[0]

        result = self._explain_one(x)

        logger.debug(
            "特征贡献分解完成 | 总评分=%s",
            result["total_score"],
        )

        return result

    def explain_batch(self, X: Any) -> list[dict[str, float]]:
        """批量特征贡献分解

        参数：
            X: 输入数据，支持字典列表或 numpy 数组

        返回：
            list[dict[str, float]]: 批量评分拆解结果
        """
        X_arr = self.inference.transform_batch(X)

        results = [self._explain_one(row) for row in X_arr]

        logger.debug(
            "批量特征贡献分解完成 | 样本数=%d",
            len(results),
        )

        return results