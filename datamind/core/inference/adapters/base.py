# datamind/core/inference/adapters/base.py

"""基础模型适配器

提供统一的模型输入转换、推理调度、能力检查和结果校验能力。

核心功能：
  - predict_proba: 单条概率预测
  - predict_proba_batch: 批量概率预测
  - decision_function: 单条对数几率预测
  - decision_function_batch: 批量对数几率预测
  - predict: 概率预测统一入口
  - predict_logit: 对数几率预测统一入口
  - to_array: 将单条特征字典转换为二维数组
  - to_array_batch: 将批量特征字典转换为二维数组
  - validate_features: 验证特征完整性和类型
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取模型能力集
  - has_capability: 检查模型能力
  - require_capability: 校验模型能力

使用示例：
  from datamind.core.inference.adapters.base import BaseModelAdapter

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
from datamind.core.inference.features import FeatureTransformer

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
        self.transformer = FeatureTransformer(
            feature_names=feature_names,
            data_types=data_types,
        )
        self.feature_names = self.transformer.feature_names
        self.data_types = self.transformer.data_types
        self.positive_class = positive_class

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
        """预测单条样本的概率

        由具体模型适配器实现。
        """
        pass

    def predict_proba_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """预测批量样本的概率

        默认逐条调用单条概率预测接口，具体模型适配器可重写此方法。
        """
        array = self.transformer.ensure_2d(
            X
        )

        logger.debug(
            "逐条执行批量概率预测",
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
        """预测单条样本的对数几率

        支持对数几率预测的模型适配器应重写此方法。
        """
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        raise NotImplementedError(
            f"{self.__class__.__name__}: "
            "未实现对数几率预测接口"
        )

    def decision_function_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """预测批量样本的对数几率

        默认逐条调用单条对数几率预测接口，具体模型适配器可重写此方法。
        """
        array = self.transformer.ensure_2d(
            X
        )

        logger.debug(
            "逐条执行批量对数几率预测",
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

            self.transformer.validate_batch(
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
        """对数几率预测统一入口"""
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

            self.transformer.validate_batch(
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
        return self.transformer.transform(features)

    def to_array_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> np.ndarray:
        """将批量特征字典转换为二维数组"""
        return self.transformer.transform_batch(features_list)

    def validate_features(
            self,
            features: dict[str, Any],
    ) -> tuple[
        list[str],
        list[tuple[str, str, str]],
    ]:
        """验证特征完整性和类型"""
        return self.transformer.validate(features)

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取模型能力集"""
        return self.capabilities

    def has_capability(
            self,
            capability: ModelCapability,
    ) -> bool:
        """检查模型能力"""
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
        """提取并统一对数几率方向"""
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
                    "暂不支持多分类对数几率输出，"
                    f"当前输出 shape={logits.shape}"
                )

            logits = logits.reshape(-1)

        elif logits.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "暂不支持多分类对数几率输出，"
                f"当前输出 shape={logits.shape}"
            )

        if not np.all(
                np.isfinite(logits)
        ):
            raise ValueError(
                f"{self.__class__.__name__}: "
                "模型返回了非法对数几率值"
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
