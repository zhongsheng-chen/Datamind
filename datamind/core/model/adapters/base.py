# datamind/core/model/adapters/base.py

"""基础模型适配器

提供统一的模型输入转换、推理调度、能力检查和结果校验能力。

核心功能：
  - predict_proba: 概率预测抽象接口
  - predict_proba_batch: 批量概率预测回退实现
  - decision_function: Logit 预测可选接口
  - decision_function_batch: 批量 Logit 预测回退实现
  - predict: 概率预测统一入口
  - predict_logit: Logit 预测统一入口
  - to_array: 特征转换
  - to_array_batch: 批量特征转换
  - validate_features: 特征校验
  - get_feature_importance: 特征重要性接口
  - get_capabilities: 获取模型能力集
  - has_capability: 检查模型能力
  - require_capability: 校验模型能力

使用示例：
  from datamind.core.model.adapters.base import BaseModelAdapter

  class CustomModelAdapter(BaseModelAdapter):
      ...
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from numbers import Integral
from typing import Any, TypeAlias, Union

import numpy as np
from numpy.typing import NDArray
import structlog

from datamind.constants import DataType
from datamind.core.capability import ModelCapability

logger = structlog.get_logger(__name__)

PredictionInput: TypeAlias = Union[
    NDArray[Any],
    dict[str, Any],
    list[dict[str, Any]],
]

PredictionResult: TypeAlias = Union[
    float,
    list[float],
]


class BaseModelAdapter(ABC):
    """统一模型适配器基类"""

    SUPPORTED_CAPABILITIES = ModelCapability.NONE

    def __init__(
            self,
            model: Any,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            positive_class: Any = 1,
    ) -> None:
        """初始化适配器

        参数：
            model: 已训练模型
            feature_names: 特征名称列表
            data_types: 特征类型映射
            positive_class: 正类标签，默认值为 1

        异常：
            ValueError: 模型为空或特征名称无效
        """
        if model is None:
            raise ValueError(
                "model 不能为空"
            )

        self.model = model
        self.feature_names = self._normalize_feature_names(
            feature_names
        )
        self.data_types = dict(
            data_types or {}
        )
        self.positive_class = positive_class

        self._feature_index = (
            {
                name: index
                for index, name in enumerate(
                    self.feature_names
                )
            }
            if self.feature_names
            else None
        )

        self.capabilities = self._detect_capabilities()

        numeric_count = sum(
            data_type == DataType.NUMERIC
            for data_type in self.data_types.values()
        )
        categorical_count = sum(
            data_type == DataType.CATEGORICAL
            for data_type in self.data_types.values()
        )

        logger.debug(
            "初始化模型适配器",
            adapter=self.__class__.__name__,
            feature_count=len(
                self.feature_names or []
            ),
            numeric_count=numeric_count,
            categorical_count=categorical_count,
            positive_class=self.positive_class,
            capabilities=int(
                self.capabilities
            ),
        )

    def _detect_capabilities(
            self,
    ) -> ModelCapability:
        """检测当前模型实例能力"""
        return self.SUPPORTED_CAPABILITIES

    @abstractmethod
    def predict_proba(
            self,
            X: np.ndarray,
    ) -> float:
        """概率预测抽象接口"""
        pass

    def predict_proba_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """批量概率预测回退实现"""
        array = self._ensure_2d(
            X
        )

        logger.debug(
            "使用批量概率预测回退方案",
            sample_count=len(array),
        )

        return [
            self.predict_proba(
                row.reshape(1, -1)
            )
            for row in array
        ]

    def decision_function(
            self,
            X: np.ndarray,
    ) -> float:
        """Logit 预测可选接口"""
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        raise NotImplementedError(
            f"{self.__class__.__name__}: "
            "未实现 Logit 预测接口"
        )

    def decision_function_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """批量 Logit 预测回退实现"""
        array = self._ensure_2d(
            X
        )

        logger.debug(
            "使用批量 Logit 预测回退方案",
            sample_count=len(array),
        )

        return [
            self.decision_function(
                row.reshape(1, -1)
            )
            for row in array
        ]

    def predict(
            self,
            X: PredictionInput,
    ) -> PredictionResult:
        """概率预测统一入口"""
        if X is None:
            raise ValueError(
                "输入不能为 None"
            )

        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        if isinstance(
                X,
                dict,
        ):
            return self.predict_proba(
                self.to_array(X)
            )

        if isinstance(
                X,
                list,
        ):
            if not X:
                return []

            self._validate_feature_list(
                X
            )
            self.require_capability(
                ModelCapability.BATCH_PREDICT
            )

            return self.predict_proba_batch(
                self.to_array_batch(X)
            )

        if isinstance(
                X,
                np.ndarray,
        ):
            if X.ndim not in (
                    1,
                    2,
            ):
                raise ValueError(
                    "仅支持 1D / 2D numpy 输入，"
                    f"当前 ndim={X.ndim}"
                )

            if X.size == 0:
                return []

            if X.ndim == 1:
                return self.predict_proba(
                    X.reshape(1, -1)
                )

            if X.ndim == 2:
                self.require_capability(
                    ModelCapability.BATCH_PREDICT
                )

                return self.predict_proba_batch(
                    X
                )

        input_type = str(
            type(X).__name__
        )

        raise TypeError(
            "不支持输入类型: "
            f"{input_type}"
        )

    def predict_logit(
            self,
            X: PredictionInput,
    ) -> PredictionResult:
        """Logit 预测统一入口"""
        if X is None:
            raise ValueError(
                "输入不能为 None"
            )

        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        if isinstance(
                X,
                dict,
        ):
            return self.decision_function(
                self.to_array(X)
            )

        if isinstance(
                X,
                list,
        ):
            if not X:
                return []

            self._validate_feature_list(
                X
            )
            self.require_capability(
                ModelCapability.BATCH_PREDICT
            )

            return self.decision_function_batch(
                self.to_array_batch(X)
            )

        if isinstance(
                X,
                np.ndarray,
        ):
            if X.ndim not in (
                    1,
                    2,
            ):
                raise ValueError(
                    "仅支持 1D / 2D numpy 输入，"
                    f"当前 ndim={X.ndim}"
                )

            if X.size == 0:
                return []

            if X.ndim == 1:
                return self.decision_function(
                    X.reshape(1, -1)
                )

            if X.ndim == 2:
                self.require_capability(
                    ModelCapability.BATCH_PREDICT
                )

                return self.decision_function_batch(
                    X
                )

        input_type = str(
            type(X).__name__
        )

        raise TypeError(
            "不支持输入类型: "
            f"{input_type}"
        )

    def to_array(
            self,
            features: dict[str, Any],
    ) -> np.ndarray:
        """将单条特征字典转换为二维数组"""
        if not features:
            raise ValueError(
                "features 不能为空"
            )

        if not self.feature_names:
            raise ValueError(
                "feature_names 不能为空"
            )

        feature_index = self._get_feature_index()
        values: list[Any] = [
            np.nan
            for _ in self.feature_names
        ]

        for name, value in features.items():
            index = feature_index.get(
                name
            )

            if index is not None:
                values[index] = self._to_value_or_nan(
                    value,
                    name,
                )

        return np.asarray(
            [values],
            dtype=object,
        )

    def to_array_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> np.ndarray:
        """将批量特征字典转换为二维数组

        该实现不依赖 pandas，确保不同运行环境下的
        字段排序和值转换行为一致。
        """
        if not features_list:
            raise ValueError(
                "features_list 不能为空"
            )

        self._validate_feature_list(
            features_list
        )

        names = self._resolve_batch_feature_names(
            features_list
        )

        return np.asarray(
            [
                [
                    self._to_value_or_nan(
                        features.get(name),
                        name,
                    )
                    for name in names
                ]
                for features in features_list
            ],
            dtype=object,
        )

    def validate_features(
            self,
            features: dict[str, Any],
    ) -> tuple[
        list[str],
        list[tuple[str, str, str]],
    ]:
        """验证特征完整性和类型"""
        missing: list[str] = []
        type_errors: list[
            tuple[str, str, str]
        ] = []

        if not self.feature_names:
            return (
                missing,
                type_errors,
            )

        for name in self.feature_names:
            value = features.get(
                name
            )

            if value is None:
                missing.append(
                    name
                )
                continue

            data_type = self.data_types.get(
                name,
                DataType.ANY,
            )

            if data_type == DataType.NUMERIC:
                valid = (
                    not isinstance(
                        value,
                        bool,
                    )
                    and isinstance(
                        value,
                        (
                            int,
                            float,
                            np.number,
                        ),
                    )
                )
                expected = "numeric"

            elif data_type == DataType.BOOLEAN:
                valid = (
                    isinstance(
                        value,
                        bool,
                    )
                    or (
                        isinstance(
                            value,
                            (
                                int,
                                float,
                                np.number,
                            ),
                        )
                        and value in (
                            0,
                            1,
                        )
                    )
                )
                expected = "boolean"

            elif data_type == DataType.CATEGORICAL:
                valid = isinstance(
                    value,
                    str,
                )
                expected = "categorical"

            else:
                valid = True
                expected = "any"

            if not valid:
                type_errors.append(
                    (
                        name,
                        expected,
                        type(value).__name__,
                    )
                )

        return (
            missing,
            type_errors,
        )

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取当前模型实例能力集"""
        return self.capabilities

    def get_positive_class_index(
            self,
    ) -> int:
        """获取正类在模型类别中的位置"""
        return self._get_positive_class_index()

    def has_capability(
            self,
            capability: ModelCapability,
    ) -> bool:
        """检查模型是否支持全部指定能力"""
        return (
            self.capabilities & capability
        ) == capability

    def require_capability(
            self,
            capability: ModelCapability,
    ) -> None:
        """校验模型能力"""
        if not self.has_capability(
                capability
        ):
            capability_name = str(
                capability.name
            )

            raise NotImplementedError(
                f"{self.__class__.__name__} "
                f"不支持能力: {capability_name}"
            )

    def get_feature_importance(
            self,
    ) -> dict[str, float]:
        """获取特征重要性"""
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        raise NotImplementedError(
            f"{self.__class__.__name__} "
            "未实现特征重要性"
        )

    def _validate_binary_model(
            self,
    ) -> None:
        """校验模型为二分类模型并解析正类标签"""
        classes = getattr(
            self.model,
            "classes_",
            None,
        )

        if classes is not None:
            self._get_positive_class_index()
            return

        class_count = getattr(
            self.model,
            "n_classes_",
            None,
        )

        if class_count is None:
            return

        if (
                isinstance(class_count, bool)
                or not isinstance(
                    class_count,
                    Integral,
                )
        ):
            raise ValueError(
                f"{self.__class__.__name__}: "
                "模型类别数必须为整数，"
                f"当前类型={type(class_count).__name__}"
            )

        resolved_class_count = int(
            class_count
        )

        if resolved_class_count != 2:
            raise ValueError(
                f"{self.__class__.__name__}: "
                "仅支持二分类模型，"
                f"当前类别数={resolved_class_count}"
            )

    def _get_positive_class_index(
            self,
    ) -> int:
        """获取正类在概率矩阵中的列位置"""
        classes = getattr(
            self.model,
            "classes_",
            None,
        )

        if classes is None:
            return 1

        class_values = np.asarray(
            classes,
            dtype=object,
        ).reshape(-1)

        if len(class_values) != 2:
            raise ValueError(
                f"{self.__class__.__name__}: "
                "仅支持二分类模型，"
                f"当前类别数={len(class_values)}"
            )

        for index, class_value in enumerate(
                class_values
        ):
            if class_value == self.positive_class:
                return index

        raise ValueError(
            f"{self.__class__.__name__}: "
            "模型类别中不存在指定正类，"
            f"positive_class={self.positive_class}, "
            f"classes={class_values.tolist()}"
        )

    def _extract_positive_probabilities(
            self,
            values: Any,
    ) -> np.ndarray:
        """提取并校验正类概率"""
        probabilities = np.asarray(
            values,
            dtype=float,
        )

        if probabilities.ndim != 2:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "仅支持二维概率预测结果，"
                f"当前输出 shape={probabilities.shape}"
            )

        class_count = int(
            probabilities.shape[-1]
        )

        if class_count != 2:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "仅支持二分类概率预测，"
                f"当前输出 shape={probabilities.shape}"
            )

        positive_index = self._get_positive_class_index()
        result = probabilities[
            :,
            positive_index,
        ]

        if (
                not np.all(
                    np.isfinite(result)
                )
                or np.any(result < 0)
                or np.any(result > 1)
        ):
            raise ValueError(
                f"{self.__class__.__name__}: "
                "模型返回了非法概率值"
            )

        return result

    def _extract_binary_logits(
            self,
            values: Any,
    ) -> np.ndarray:
        """提取并统一为指定正类方向的 Logit"""
        logits = np.asarray(
            values,
            dtype=float,
        )

        if logits.ndim == 0:
            logits = logits.reshape(1)

        elif logits.ndim == 2:
            output_count = int(
                logits.shape[-1]
            )

            if output_count != 1:
                raise NotImplementedError(
                    f"{self.__class__.__name__}: "
                    "暂不支持多分类 Logit 输出，"
                    f"当前输出 shape={logits.shape}"
                )

            logits = logits.reshape(-1)

        elif logits.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "暂不支持多分类 Logit 输出，"
                f"当前输出 shape={logits.shape}"
            )

        if not np.all(
                np.isfinite(logits)
        ):
            raise ValueError(
                f"{self.__class__.__name__}: "
                "模型返回了非法 Logit 值"
            )

        if self._get_positive_class_index() == 0:
            return -logits

        return logits

    @staticmethod
    def _build_feature_importance(
            values: Any,
            *,
            names: Iterable[Any] | None = None,
    ) -> dict[str, float]:
        """构造特征重要性字典并校验数量"""
        importance = np.asarray(
            values,
            dtype=float,
        ).reshape(-1)

        if not np.all(
                np.isfinite(importance)
        ):
            raise ValueError(
                "特征重要性包含非有限数值"
            )

        resolved_names = (
            [
                str(name)
                for name in names
            ]
            if names is not None
            else [
                f"f{index}"
                for index in range(
                    len(importance)
                )
            ]
        )

        if len(resolved_names) != len(importance):
            raise ValueError(
                "特征名称数量与特征重要性数量不一致: "
                f"feature_count={len(resolved_names)}, "
                f"importance_count={len(importance)}"
            )

        return {
            name: float(value)
            for name, value in zip(
                resolved_names,
                importance,
                strict=True,
            )
        }

    @staticmethod
    def _ensure_2d(
            X: np.ndarray,
    ) -> np.ndarray:
        """确保输入为二维数组"""
        array = np.asarray(
            X
        )

        if array.ndim == 1:
            return array.reshape(
                1,
                -1,
            )

        if array.ndim != 2:
            raise ValueError(
                "仅支持 1D / 2D numpy 输入，"
                f"当前 ndim={array.ndim}"
            )

        return array

    @staticmethod
    def _to_value_or_nan(
            value: Any,
            feature_name: str | None = None,
    ) -> Any:
        """将输入值转换为模型输入值"""
        if value is None:
            return np.nan

        if isinstance(
                value,
                bool,
        ):
            return float(
                value
            )

        if isinstance(
                value,
                (
                    int,
                    float,
                    np.integer,
                    np.floating,
                ),
        ):
            return float(
                value
            )

        if isinstance(
                value,
                str,
        ):
            return value

        logger.debug(
            "特征类型未标准化",
            feature=feature_name,
            value_type=type(
                value
            ).__name__,
        )

        return value

    def _get_feature_index(
            self,
    ) -> dict[str, int]:
        """获取特征名称到位置的映射"""
        if self._feature_index is not None:
            return self._feature_index

        if not self.feature_names:
            raise ValueError(
                "feature_names 不能为空"
            )

        self._feature_index = {
            name: index
            for index, name in enumerate(
                self.feature_names
            )
        }

        return self._feature_index

    def _resolve_batch_feature_names(
            self,
            features_list: list[dict[str, Any]],
    ) -> list[str]:
        """解析批量转换使用的特征顺序"""
        if self.feature_names:
            return self.feature_names

        names = sorted({
            name
            for features in features_list
            for name in features
        })

        if not names:
            raise ValueError(
                "批量特征中不存在可用字段"
            )

        return names

    @staticmethod
    def _validate_feature_list(
            features_list: list[Any],
    ) -> None:
        """校验批量输入中的每个元素均为字典"""
        invalid_index = next(
            (
                index
                for index, features in enumerate(
                    features_list
                )
                if not isinstance(
                    features,
                    dict,
                )
            ),
            None,
        )

        if invalid_index is not None:
            raise TypeError(
                "批量输入必须全部为特征字典，"
                f"第 {invalid_index} 个元素类型为 "
                f"{type(features_list[invalid_index]).__name__}"
            )

    @staticmethod
    def _normalize_feature_names(
            feature_names: list[str] | None,
    ) -> list[str] | None:
        """校验并复制特征名称列表"""
        if feature_names is None:
            return None

        normalized = list(
            feature_names
        )

        if not normalized:
            return None

        if any(
                not isinstance(name, str)
                or not name.strip()
                for name in normalized
        ):
            raise ValueError(
                "feature_names 必须是非空字符串列表"
            )

        if len(normalized) != len(
                set(normalized)
        ):
            raise ValueError(
                "feature_names 不能包含重复名称"
            )

        return normalized
