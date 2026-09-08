"""CatBoost 模型适配器

为 CatBoost 二分类模型提供概率预测和特征重要性接口。

核心功能：
  - predict_proba: 概率预测
  - predict_proba_batch: 批量概率预测
  - get_feature_importance: 获取特征重要性

使用示例：
  import numpy as np
  from catboost import CatBoostClassifier

  from datamind.core.inference.adapters.catboost import CatBoostAdapter

  X_train = np.array([
      [25, 5000],
      [45, 12000],
      [32, 8000],
      [50, 15000],
  ])

  y_train = np.array([
      1,
      0,
      1,
      0,
  ])

  model = CatBoostClassifier(
      verbose=False,
  )

  model.fit(
      X_train,
      y_train,
  )

  adapter = CatBoostAdapter(
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
"""

from collections.abc import (
    Callable,
    Iterable,
)
from typing import Any

import numpy as np
import structlog

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.inference.adapters.base import BaseModelAdapter

logger = structlog.get_logger(__name__)


class CatBoostAdapter(BaseModelAdapter):
    """CatBoost 二分类模型适配器"""

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

        self._validate_classifier_model()

    def _detect_capabilities(
            self,
    ) -> ModelCapability:
        """检测当前 CatBoost 模型能力"""
        capabilities = ModelCapability.NONE

        supports_proba = callable(
            getattr(
                self.model,
                "predict_proba",
                None,
            )
        )

        supports_importance = callable(
            getattr(
                self.model,
                "get_feature_importance",
                None,
            )
        )

        if supports_proba:
            capabilities |= (
                ModelCapability.PREDICT_PROBA
                | ModelCapability.BATCH_PREDICT
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
            "CatBoost 概率预测成功",
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
            "CatBoost 批量概率预测成功",
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

        importance = np.asarray(
            self.model.get_feature_importance(
                type="PredictionValuesChange",
            ),
            dtype=float,
        )

        importance_count = int(
            importance.size
        )

        names = self._resolve_feature_names(
            importance_count=importance_count,
        )

        result = self._build_feature_importance(
            importance,
            names=names,
        )

        logger.debug(
            "CatBoost 特征重要性计算完成",
            importance_type="PredictionValuesChange",
            feature_count=len(result),
        )

        return result

    def _validate_classifier_model(
            self,
    ) -> None:
        """校验模型为已训练的 CatBoost 二分类模型"""
        if not callable(
                getattr(
                    self.model,
                    "predict_proba",
                    None,
                )
        ):
            raise TypeError(
                f"{self.__class__.__name__}: "
                "仅支持提供 predict_proba 接口的 "
                "CatBoost 分类模型"
            )

        is_fitted = getattr(
            self.model,
            "is_fitted",
            None,
        )

        if isinstance(
                is_fitted,
                Callable,
        ):
            model_is_fitted = self.model.is_fitted()

            if not model_is_fitted:
                raise ValueError(
                    f"{self.__class__.__name__}: "
                    "模型尚未训练"
                )

        classes = getattr(
            self.model,
            "classes_",
            None,
        )

        if classes is None:
            raise ValueError(
                f"{self.__class__.__name__}: "
                "模型尚未训练或不属于分类模型"
            )

        self._validate_binary_model()

    def _predict_positive_probabilities(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """执行模型预测并提取正类概率"""
        array = self.transformer.ensure_2d(
            X
        )

        values = self.model.predict_proba(
            array
        )

        return self._extract_positive_probabilities(
            values
        )

    def _resolve_feature_names(
            self,
            *,
            importance_count: int,
    ) -> list[str]:
        """解析特征名称"""
        configured_names = (
            list(self.feature_names)
            if self.feature_names
            else None
        )

        model_names = self._to_feature_names(
            getattr(
                self.model,
                "feature_names_",
                None,
            )
        )

        if configured_names is not None:
            names = configured_names

        elif model_names is not None:
            names = model_names

        else:
            names = [
                f"f{index}"
                for index in range(
                    importance_count
                )
            ]

        if len(names) != importance_count:
            raise ValueError(
                "特征名称数量与特征重要性数量不一致: "
                f"names={len(names)}, "
                f"importance={importance_count}"
            )

        return names

    @staticmethod
    def _to_feature_names(
            values: Any,
    ) -> list[str] | None:
        """将特征名称转换为字符串列表"""
        if (
                values is None
                or isinstance(
                    values,
                    (
                        str,
                        bytes,
                    ),
                )
                or not isinstance(
                    values,
                    Iterable,
                )
        ):
            return None

        names = [
            str(name)
            for name in values
        ]

        return names or None
