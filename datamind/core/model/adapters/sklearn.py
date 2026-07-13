# datamind/core/model/adapters/sklearn.py

"""Sklearn 模型适配器

为 Sklearn 二分类模型提供概率预测和特征重要性接口，
逻辑回归模型额外提供 Logit 预测接口。

核心功能：
  - predict_proba: 概率预测
  - predict_proba_batch: 批量概率预测
  - decision_function: 逻辑回归 Logit 预测
  - decision_function_batch: 逻辑回归批量 Logit 预测
  - get_feature_importance: 获取特征重要性

使用示例：
  import numpy as np
  from sklearn.linear_model import LogisticRegression

  from datamind.core.model.adapters.sklearn import SklearnAdapter

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

  adapter = SklearnAdapter(
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

  probability = adapter.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })

  logit = adapter.predict_logit({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

from typing import Any

import numpy as np
import structlog
from sklearn.linear_model import (
    LogisticRegression,
    LogisticRegressionCV,
)

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.model.adapters.base import BaseModelAdapter

logger = structlog.get_logger(__name__)

_LOGISTIC_REGRESSION_TYPES = (
    LogisticRegression,
    LogisticRegressionCV,
)


class SklearnAdapter(BaseModelAdapter):
    """Sklearn 二分类模型适配器"""

    def __init__(
            self,
            model: Any,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            positive_class: Any = 1,
    ) -> None:
        super().__init__(
            model=model,
            feature_names=feature_names,
            data_types=data_types,
            positive_class=positive_class,
        )

        self._validate_binary_model()

    def _detect_capabilities(
            self,
    ) -> ModelCapability:
        """检测当前 Sklearn 模型能力"""
        capabilities = ModelCapability.NONE

        supports_proba = callable(
            getattr(
                self.model,
                "predict_proba",
                None,
            )
        )

        supports_log_odds = (
            isinstance(
                self.model,
                _LOGISTIC_REGRESSION_TYPES,
            )
            and callable(
                getattr(
                    self.model,
                    "decision_function",
                    None,
                )
            )
            and getattr(
                self.model,
                "coef_",
                None,
            ) is not None
            and getattr(
                self.model,
                "intercept_",
                None,
            ) is not None
        )

        supports_importance = (
            getattr(
                self.model,
                "feature_importances_",
                None,
            ) is not None
            or getattr(
                self.model,
                "coef_",
                None,
            ) is not None
        )

        if supports_proba:
            capabilities |= (
                ModelCapability.PREDICT_PROBA
                | ModelCapability.BATCH_PREDICT
            )

        if supports_log_odds:
            capabilities |= (
                ModelCapability.PREDICT_LOG_ODDS
            )

        if supports_importance:
            capabilities |= (
                ModelCapability.FEATURE_IMPORTANCE
            )

        return capabilities

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> float:
        """概率预测"""
        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        probabilities = (
            self._predict_positive_probabilities(
                X
            )
        )

        result = float(
            probabilities[0]
        )

        logger.debug(
            "Sklearn 概率预测成功",
            probability=result,
        )

        return result

    def predict_proba_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """批量概率预测"""
        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )
        self.require_capability(
            ModelCapability.BATCH_PREDICT
        )

        probabilities = (
            self._predict_positive_probabilities(
                X
            )
        )

        result = [
            float(probability)
            for probability in probabilities
        ]

        logger.debug(
            "Sklearn 批量概率预测成功",
            sample_count=len(result),
        )

        return result

    def decision_function(
            self,
            X: np.ndarray,
    ) -> float:
        """逻辑回归 Logit 预测"""
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        logits = self._predict_positive_logits(
            X
        )

        result = float(
            logits[0]
        )

        logger.debug(
            "Sklearn Logit 预测成功",
            logit=result,
        )

        return result

    def decision_function_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """逻辑回归批量 Logit 预测"""
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )
        self.require_capability(
            ModelCapability.BATCH_PREDICT
        )

        logits = self._predict_positive_logits(
            X
        )

        result = [
            float(logit)
            for logit in logits
        ]

        logger.debug(
            "Sklearn 批量 Logit 预测成功",
            sample_count=len(result),
        )

        return result

    def get_feature_importance(
            self,
    ) -> dict[str, float]:
        """获取特征重要性"""
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        feature_importances = getattr(
            self.model,
            "feature_importances_",
            None,
        )

        if feature_importances is not None:
            importance = np.asarray(
                feature_importances,
                dtype=float,
            )

            source = "feature_importances_"

        else:
            coefficients = np.asarray(
                self.model.coef_,
                dtype=float,
            )

            importance = self._extract_coefficient_importance(
                coefficients
            )

            source = "coef_"

        result = self._build_feature_importance(
            importance,
            names=self.feature_names,
        )

        logger.debug(
            "Sklearn 特征重要性计算完成",
            source=source,
            feature_count=len(result),
        )

        return result

    def _predict_positive_probabilities(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """执行模型预测并提取正类概率"""
        array = self._ensure_2d(
            X
        )

        values = self.model.predict_proba(
            array
        )

        return self._extract_positive_probabilities(
            values
        )

    def _predict_positive_logits(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """执行逻辑回归预测并提取正类 Logit"""
        array = self._ensure_2d(
            X
        )

        values = np.asarray(
            self.model.decision_function(
                array
            ),
            dtype=float,
        )

        if values.ndim == 0:
            logits = values.reshape(
                1
            )

        elif values.ndim == 1:
            logits = values

        elif (
                values.ndim == 2
                and values.shape[-1] == 1
        ):
            logits = values.reshape(
                -1
            )

        else:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "不支持当前 decision_function 输出，"
                f"shape={values.shape}"
            )

        direction = (
            1.0
            if self.get_positive_class_index() == 1
            else -1.0
        )

        return (
            logits
            * direction
        )

    def _extract_coefficient_importance(
            self,
            coefficients: np.ndarray,
    ) -> np.ndarray:
        """提取正类对应的系数绝对值"""
        if coefficients.ndim == 1:
            return np.abs(
                coefficients
            )

        if coefficients.ndim != 2:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "不支持当前 coef_ 维度，"
                f"shape={coefficients.shape}"
            )

        class_count = int(
            coefficients.shape[-2]
        )

        if class_count == 1:
            selected = coefficients.reshape(
                -1
            )

        elif class_count == 2:
            positive_index = (
                self.get_positive_class_index()
            )

            selected = coefficients[
                positive_index
            ]

        else:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "暂不支持多分类 coef_，"
                f"当前 shape={coefficients.shape}"
            )

        return np.abs(
            selected
        )
