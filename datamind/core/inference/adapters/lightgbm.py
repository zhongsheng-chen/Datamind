"""LightGBM 模型适配器.

为采用 Sklearn API 的 LightGBM 二分类模型提供概率预测和
Gain 特征重要性接口。

核心功能：
  - predict_proba: 概率预测
  - predict_proba_batch: 批量概率预测
  - get_feature_importance: 获取 Gain 特征重要性

使用示例：
  import numpy as np
  from lightgbm import LGBMClassifier

  from datamind.core.inference.adapters.lightgbm import LightGBMAdapter

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

  model = LGBMClassifier()
  model.fit(
      X_train,
      y_train,
  )

  adapter = LightGBMAdapter(
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
from typing import (
    Any,
    TypeVar,
)

import numpy as np
import structlog

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.inference.adapters.base import BaseModelAdapter

logger = structlog.get_logger(__name__)

_Result = TypeVar("_Result")


def _call_model_method(
        method: Callable[..., _Result],
        *args: object,
        **kwargs: object,
) -> _Result:
    """调用已验证的模型方法."""
    return method(*args, **kwargs)


class LightGBMAdapter(BaseModelAdapter):
    """LightGBM 二分类模型适配器."""

    def __init__(
            self,
            model: Any,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            positive_class: Any = 1,
    ) -> None:
        """初始化 LightGBM 模型适配器.

        参数：
            model: 已训练模型
            feature_names: 特征名称列表（可选）
            data_types: 特征类型映射（可选）
            positive_class: 正类标签，默认值为 1
        """
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
        """检测当前 LightGBM 模型能力."""
        capabilities = ModelCapability.NONE

        supports_sklearn_proba = callable(
            getattr(
                self.model,
                "predict_proba",
                None,
            )
        )
        supports_native_proba = (
            callable(getattr(self.model, "predict", None))
            and callable(
                getattr(
                    self.model,
                    "feature_importance",
                    None,
                )
            )
        )

        model_state = getattr(
            self.model,
            "__dict__",
            {},
        )

        supports_importance = (
            model_state.get("_Booster") is not None
            or callable(
                getattr(
                    self.model,
                    "feature_importance",
                    None,
                )
            )
        )

        if supports_sklearn_proba or supports_native_proba:
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
        """概率预测."""
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
            "LightGBM 概率预测成功",
            probability=result,
        )

        return result

    def predict_proba_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """批量概率预测."""
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
            "LightGBM 批量概率预测成功",
            sample_count=len(result),
        )

        return result

    def get_feature_importance(
            self,
    ) -> dict[str, float]:
        """获取 Gain 特征重要性."""
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        booster = getattr(
            self.model,
            "booster_",
            self.model,
        )

        importance_method: Callable[..., object] | None = getattr(
            booster,
            "feature_importance",
            None,
        )

        if not callable(importance_method):
            raise RuntimeError(
                f"{self.__class__.__name__}: "
                "模型不提供特征重要性接口"
            )

        importance = np.asarray(
            _call_model_method(
                importance_method,
                importance_type="gain"
            ),
            dtype=float,
        )

        importance_count = int(
            importance.size
        )

        name_method: Callable[
            [],
            list[str],
        ] | None = getattr(
            booster,
            "feature_name",
            None,
        )

        if callable(name_method):
            booster_names = _call_model_method(
                name_method
            )
        else:
            booster_names = None

        names = self._resolve_feature_names(
            booster_names=booster_names,
            importance_count=importance_count,
        )

        result = self._build_feature_importance(
            importance,
            names=names,
        )

        logger.debug(
            "LightGBM 特征重要性计算完成",
            importance_type="gain",
            feature_count=len(result),
        )

        return result

    def _validate_classifier_model(
            self,
    ) -> None:
        """校验模型为已训练的 LightGBM 二分类模型."""
        supports_sklearn = callable(
            getattr(
                self.model,
                "predict_proba",
                None,
            )
        )
        supports_native = (
            callable(getattr(self.model, "predict", None))
            and callable(
                getattr(
                    self.model,
                    "feature_importance",
                    None,
                )
            )
        )

        if not supports_sklearn and not supports_native:
            raise TypeError(
                f"{self.__class__.__name__}: "
                "仅支持 LGBMClassifier 或 Booster 形式的 "
                "LightGBM 分类模型"
            )

        classes = getattr(
            self.model,
            "classes_",
            None,
        )

        if classes is None and not supports_native:
            raise ValueError(
                f"{self.__class__.__name__}: "
                "模型尚未训练或不属于分类模型"
            )

        booster = getattr(self.model, "booster_", None)

        if booster is None and not supports_native:
            raise ValueError(
                f"{self.__class__.__name__}: "
                "模型尚未训练，缺少 booster_"
            )

        self._validate_binary_model()

    def _predict_positive_probabilities(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """执行模型预测并提取正类概率."""
        array = self.transformer.ensure_2d(
            X
        )

        predict_proba: Callable[
            [np.ndarray],
            object,
        ] | None = getattr(
            self.model,
            "predict_proba",
            None,
        )

        if callable(predict_proba):
            values = _call_model_method(
                predict_proba,
                array,
            )
        else:
            positive = np.asarray(
                self.model.predict(array),
                dtype=float,
            ).reshape(-1)
            if self.positive_class == 0:
                positive = 1.0 - positive
            elif self.positive_class != 1:
                raise ValueError(
                    f"{self.__class__.__name__}: "
                    "原生 Booster 的 positive_class "
                    "仅支持 0 或 1"
                )
            values = np.column_stack((
                1.0 - positive,
                positive,
            ))

        return self._extract_positive_probabilities(
            values
        )

    def _resolve_feature_names(
            self,
            *,
            booster_names: Any,
            importance_count: int,
    ) -> list[str]:
        """解析特征名称."""
        configured_names = (
            list(self.feature_names)
            if self.feature_names
            else None
        )

        resolved_booster_names = (
            self._to_feature_names(
                booster_names
            )
        )

        model_names = self._to_feature_names(
            getattr(
                self.model,
                "feature_names_in_",
                None,
            )
        )

        if configured_names is not None:
            names = configured_names

        elif resolved_booster_names is not None:
            names = resolved_booster_names

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
        """将特征名称转换为字符串列表."""
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
