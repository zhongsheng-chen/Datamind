# datamind/core/scoring/contrib.py

"""评分贡献分解

提供评分贡献分解能力，目前支持逻辑回归模型。

核心功能：
  - explain: 计算评分贡献
  - explain_batch: 批量计算评分贡献

注意：
  - LRContrib 根据二分类逻辑回归模型的系数和截距，
    将未截断原始评分分解为截距评分和各特征评分贡献。
  - 仅适用于声明 PREDICT_LOG_ODDS 能力，并提供 coef_ 和
    intercept_ 属性的二分类逻辑回归模型。
  - 输入特征必须与模型系数使用相同的顺序和数值变换。
  - 评分贡献基于未截断原始评分计算，不应用 min_score 和
    max_score 限制。
  - 评分贡献满足以下关系：

      logit = Σ(w_i * x_i) + b
      raw_score = offset - factor * logit
      intercept_score = offset - factor * b
      feature_score_i = -factor * w_i * x_i

使用示例：
  import numpy as np
  from sklearn.linear_model import LogisticRegression

  from datamind.core.inference import Inference
  from datamind.core.scoring.contrib import LRContrib

  X_train = np.array([
      [25, 80000, 0.20, 0.25, 0],
      [45, 150000, 0.38, 0.62, 2],
      [32, 100000, 0.28, 0.35, 0],
      [50, 180000, 0.42, 0.70, 3],
  ])

  y_train = np.array([
      1,
      0,
      1,
      0,
  ])

  model = LogisticRegression()
  model.fit(
      X_train,
      y_train,
  )

  inference = Inference(
      model=model,
      feature_names=[
          "age",
          "annual_income",
          "debt_to_income_ratio",
          "credit_utilization_ratio",
          "delinquency_count",
      ],
      positive_class=1,
  )

  contrib = LRContrib(
      inference=inference
  )

  result = contrib.explain({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

import math
from typing import (
    Any,
    ClassVar,
)

import numpy as np
import structlog

from datamind.core.capability import (
    ModelCapability,
    ScorecardCapability,
)
from datamind.core.inference import Inference
from datamind.core.scoring.base import BaseScorer
from datamind.core.scoring.transformer import ScoreTransformer

logger = structlog.get_logger(__name__)


class LRContrib(BaseScorer):
    """逻辑回归评分贡献分解器"""

    SUPPORTED_CAPABILITIES: ClassVar[
        ScorecardCapability
    ] = ScorecardCapability.SCORECARD_FEATURE_SCORE

    _RESERVED_NAMES: ClassVar[
        set[str]
    ] = {
        "intercept_score",
        "feature_score",
        "raw_score",
    }

    def __init__(
            self,
            inference: Inference,
            transformer: ScoreTransformer | None = None,
    ) -> None:
        """初始化评分贡献分解器

        参数：
            inference: 统一模型推理接口
            transformer: 评分转换器，为 None 时使用默认配置

        异常：
            NotImplementedError: 模型不支持 Logit 或缺少线性模型参数
            ValueError: 模型参数或特征名称不符合要求
        """
        inference.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        self.inference = inference
        self.transformer = (
            transformer
            if transformer is not None
            else ScoreTransformer()
        )

        model = inference.adapter.model

        coefficients = getattr(
            model,
            "coef_",
            None,
        )

        if coefficients is None:
            raise NotImplementedError(
                "LRContrib 仅支持具有 coef_ 的逻辑回归模型"
            )

        coefficient_array = np.asarray(
            coefficients,
            dtype=float,
        )

        if coefficient_array.ndim != 2:
            raise NotImplementedError(
                "LRContrib 仅支持二维 coef_，"
                f"当前 shape={coefficient_array.shape}"
            )

        output_count = int(
            coefficient_array.shape[-2]
        )

        if output_count != 1:
            raise NotImplementedError(
                "LRContrib 仅支持二分类单输出逻辑回归模型，"
                f"当前 coef_ shape={coefficient_array.shape}"
            )

        direction = (
            1.0
            if inference.adapter.get_positive_class_index() == 1
            else -1.0
        )

        self.coef = (
            coefficient_array.reshape(-1)
            * direction
        )

        intercepts = getattr(
            model,
            "intercept_",
            None,
        )

        if intercepts is None:
            raise NotImplementedError(
                "LRContrib 仅支持具有 intercept_ 的逻辑回归模型"
            )

        intercept_array = np.asarray(
            intercepts,
            dtype=float,
        ).reshape(-1)

        if intercept_array.size != 1:
            raise NotImplementedError(
                "LRContrib 仅支持单一截距的二分类模型，"
                f"当前 intercept_ shape={intercept_array.shape}"
            )

        self.intercept = float(
            intercept_array[0]
            * direction
        )

        self.factor = self.transformer.factor
        self.offset = self.transformer.offset

        self.feature_names = self._resolve_feature_names(
            coefficient_count=int(
                self.coef.size
            )
        )

        logger.debug(
            "初始化逻辑回归评分贡献分解器",
            feature_count=int(
                self.coef.size
            ),
            intercept=self.intercept,
        )

    def explain(
            self,
            X: dict[str, Any],
    ) -> dict[str, float]:
        """计算评分贡献"""
        self.require_capability(
            ScorecardCapability.SCORECARD_FEATURE_SCORE
        )

        array = self.inference.transform(
            X
        )

        result = self._explain_row(
            array.reshape(-1)
        )

        logger.debug(
            "评分贡献计算完成",
            feature_count=len(
                self.feature_names
            ),
            raw_score=result["raw_score"],
        )

        return result

    def explain_batch(
            self,
            X: list[dict[str, Any]],
    ) -> list[dict[str, float]]:
        """批量计算评分贡献"""
        self.require_capability(
            ScorecardCapability.SCORECARD_FEATURE_SCORE
        )

        array = self.inference.transform_batch(
            X
        )

        result = [
            self._explain_row(
                row
            )
            for row in array
        ]

        logger.debug(
            "批量评分贡献计算完成",
            sample_count=len(result),
        )

        return result

    def _explain_row(
            self,
            values: np.ndarray,
    ) -> dict[str, float]:
        """分解数组对应的评分贡献"""
        row = np.asarray(
            values
        ).reshape(-1)

        coefficient_count = int(
            self.coef.size
        )

        if row.size != coefficient_count:
            raise ValueError(
                "输入特征数量与模型系数数量不一致: "
                f"feature_count={row.size}, "
                f"coefficient_count={coefficient_count}"
            )

        contributions: dict[str, float] = {}
        feature_score = 0.0

        for name, value, coefficient in zip(
                self.feature_names,
                row,
                self.coef,
                strict=True,
        ):
            numeric_value = self._require_finite_float(
                value,
                feature_name=name,
            )

            contribution = (
                -self.factor
                * float(coefficient)
                * numeric_value
            )

            contributions[
                name
            ] = contribution

            feature_score += contribution

        intercept_score = (
            self.offset
            - self.factor * self.intercept
        )

        raw_score = (
            intercept_score
            + feature_score
        )

        return {
            "intercept_score": intercept_score,
            "feature_score": feature_score,
            "raw_score": raw_score,
            **contributions,
        }

    def _resolve_feature_names(
            self,
            *,
            coefficient_count: int,
    ) -> list[str]:
        """解析并校验特征名称"""
        configured_names = (
            list(
                self.inference.adapter.feature_names
            )
            if self.inference.adapter.feature_names
            else None
        )

        if configured_names is None:
            names = [
                f"f{index}"
                for index in range(
                    coefficient_count
                )
            ]

        else:
            names = configured_names

        if len(names) != coefficient_count:
            raise ValueError(
                "特征名称数量与模型系数数量不一致: "
                f"feature_count={len(names)}, "
                f"coefficient_count={coefficient_count}"
            )

        reserved_names = (
            self._RESERVED_NAMES
            & set(names)
        )

        if reserved_names:
            reserved_text = ", ".join(
                sorted(
                    reserved_names
                )
            )

            raise ValueError(
                "特征名称与评分贡献保留字段冲突: "
                f"{reserved_text}"
            )

        return names

    @staticmethod
    def _require_finite_float(
            value: Any,
            *,
            feature_name: str,
    ) -> float:
        """校验并返回有限浮点数"""
        if value is None:
            raise ValueError(
                "逻辑回归特征不能为空，"
                f"feature={feature_name}"
            )

        try:
            numeric_value = float(
                value
            )
        except (
                TypeError,
                ValueError,
        ) as exc:
            value_type = str(
                type(value).__name__
            )

            raise ValueError(
                "逻辑回归特征必须是数值，"
                f"feature={feature_name}, "
                f"value_type={value_type}"
            ) from exc

        if not math.isfinite(
                numeric_value
        ):
            raise ValueError(
                "逻辑回归特征必须是有限数值，"
                f"feature={feature_name}"
            )

        return numeric_value
