"""XGBoost 模型适配器

为采用 Sklearn API 的 XGBoost 二分类模型提供概率预测和
Gain 特征重要性接口。

核心功能：
  - predict_proba: 概率预测
  - predict_proba_batch: 批量概率预测
  - get_feature_importance: 获取 Gain 特征重要性

使用示例：
  import numpy as np
  from xgboost import XGBClassifier

  from datamind.core.inference.adapters.xgboost import XGBoostAdapter

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

  model = XGBClassifier()
  model.fit(
      X_train,
      y_train,
  )

  adapter = XGBoostAdapter(
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

from collections.abc import Iterable
from numbers import Integral
from typing import Any

import numpy as np
import structlog

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.inference.adapters.base import BaseModelAdapter

logger = structlog.get_logger(__name__)


class XGBoostAdapter(BaseModelAdapter):
    """XGBoost 二分类模型适配器"""

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
        """检测当前 XGBoost 模型能力"""
        capabilities = ModelCapability.NONE

        supports_proba = callable(
            getattr(
                self.model,
                "predict_proba",
                None,
            )
        )

        supports_booster = callable(
            getattr(
                self.model,
                "get_booster",
                None,
            )
        )

        if supports_proba:
            capabilities |= (
                ModelCapability.PREDICT_PROBA
                | ModelCapability.BATCH_PREDICT
            )

        if supports_booster:
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
            "XGBoost 概率预测成功",
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
            "XGBoost 批量概率预测成功",
            sample_count=len(result),
        )

        return result

    def get_feature_importance(
            self,
    ) -> dict[str, float]:
        """获取 Gain 特征重要性"""
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        booster = self.model.get_booster()

        raw_score = booster.get_score(
            importance_type="gain"
        )

        score = {
            str(name): float(value)
            for name, value in raw_score.items()
        }

        feature_mapping = (
            self._resolve_feature_mapping(
                booster=booster,
                score=score,
            )
        )

        names = [
            display_name
            for display_name, _ in feature_mapping
        ]

        values = [
            score.get(
                booster_name,
                0.0,
            )
            for _, booster_name in feature_mapping
        ]

        result = self._build_feature_importance(
            values,
            names=names,
        )

        logger.debug(
            "XGBoost 特征重要性计算完成",
            importance_type="gain",
            feature_count=len(result),
        )

        return result

    def _validate_classifier_model(
            self,
    ) -> None:
        """校验模型为已训练的 XGBoost 二分类模型"""
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
                "XGBoost 分类模型"
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

    def _resolve_feature_mapping(
            self,
            *,
            booster: Any,
            score: dict[str, float],
    ) -> list[tuple[str, str]]:
        """解析展示特征名与 Booster 特征名的对应关系"""
        configured_names = (
            list(self.feature_names)
            if self.feature_names
            else None
        )

        booster_names = self._to_feature_names(
            getattr(
                booster,
                "feature_names",
                None,
            )
        )

        model_names = self._to_feature_names(
            getattr(
                self.model,
                "feature_names_in_",
                None,
            )
        )

        feature_count = self._get_feature_count()

        if configured_names is not None:
            display_names = configured_names

        elif booster_names is not None:
            display_names = booster_names

        elif model_names is not None:
            display_names = model_names

        elif feature_count is not None:
            display_names = [
                f"f{index}"
                for index in range(
                    feature_count
                )
            ]

        else:
            display_names = sorted(
                score,
                key=self._feature_sort_key,
            )

        if booster_names is not None:
            internal_names = booster_names

        elif feature_count is not None:
            internal_names = [
                f"f{index}"
                for index in range(
                    feature_count
                )
            ]

        elif configured_names is not None:
            internal_names = [
                f"f{index}"
                for index in range(
                    len(configured_names)
                )
            ]

        elif model_names is not None:
            internal_names = [
                f"f{index}"
                for index in range(
                    len(model_names)
                )
            ]

        else:
            internal_names = sorted(
                score,
                key=self._feature_sort_key,
            )

        if feature_count is not None:
            if len(display_names) != feature_count:
                raise ValueError(
                    "特征名称数量与模型特征数量不一致: "
                    f"names={len(display_names)}, "
                    f"model={feature_count}"
                )

            if len(internal_names) != feature_count:
                raise ValueError(
                    "Booster 特征名称数量与模型特征数量不一致: "
                    f"names={len(internal_names)}, "
                    f"model={feature_count}"
                )

        if len(display_names) != len(
                internal_names
        ):
            raise ValueError(
                "展示特征名称与 Booster 特征名称数量不一致: "
                f"display={len(display_names)}, "
                f"booster={len(internal_names)}"
            )

        return list(
            zip(
                display_names,
                internal_names,
                strict=True,
            )
        )

    def _get_feature_count(
            self,
    ) -> int | None:
        """获取模型特征数量"""
        value = getattr(
            self.model,
            "n_features_in_",
            None,
        )

        if value is None:
            return None

        if (
                isinstance(value, bool)
                or not isinstance(
                    value,
                    Integral,
                )
        ):
            raise ValueError(
                "模型特征数量必须为整数，"
                f"当前类型={type(value).__name__}"
            )

        feature_count = int(
            value
        )

        if feature_count < 1:
            raise ValueError(
                "模型特征数量必须大于 0"
            )

        return feature_count

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

    @staticmethod
    def _feature_sort_key(
            name: str,
    ) -> tuple[int, int | str]:
        """生成 XGBoost 特征名称排序键"""
        if (
                name.startswith("f")
                and name[1:].isdigit()
        ):
            return (
                0,
                int(name[1:]),
            )

        return (
            1,
            name,
        )
