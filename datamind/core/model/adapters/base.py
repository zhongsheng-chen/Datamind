# datamind/core/model/adapters/base.py

"""基础模型适配器

提供统一的模型接口规范，所有框架适配器必须继承此类。

核心功能：
  - predict_proba: 预测违约概率（抽象方法，子类必须实现）
  - decision_function: 获取原始 Logit 值（抽象方法，子类必须实现）
  - predict_proba_batch: 批量预测概率（子类可重写优化）
  - decision_function_batch: 批量获取 Logit（子类可重写优化）
  - predict: 统一概率预测接口
  - predict_logit: 统一 Logit 预测接口
  - to_array: 特征字典转 numpy 数组
  - to_array_batch: 批量特征字典转 numpy 数组
  - validate_features: 验证特征完整性和类型
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取当前模型实例能力集
  - has_capability: 检查模型能力
  - require_capability: 校验模型能力

使用示例：
  from datamind.core.model.adapters.base import BaseModelAdapter

  class CustomModelAdapter(BaseModelAdapter):
      ...
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import structlog

from datamind.constants import DataType
from datamind.core.capability import ModelCapability

logger = structlog.get_logger(__name__)


class BaseModelAdapter(ABC):
    """统一模型接口

    所有框架适配器的基类。

    属性：
        SUPPORTED_CAPABILITIES: 默认静态能力声明
        model: 原始模型对象
        feature_names: 特征名称列表
        data_types: 特征数据类型映射
        capabilities: 当前模型实例能力集
    """

    SUPPORTED_CAPABILITIES = ModelCapability.NONE

    def __init__(
            self,
            model,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
    ):
        """初始化适配器

        参数：
            model: 训练好的模型
            feature_names: 特征名称列表，用于保证特征顺序
            data_types: 特征数据类型映射，用于类型验证
        """
        self.model = model
        self.feature_names = feature_names
        self.data_types = data_types or {}

        self._feature_index: dict[str, int] | None = (
            {
                name: idx
                for idx, name in enumerate(
                feature_names
            )
            }
            if feature_names
            else None
        )

        self.capabilities = (
            self._detect_capabilities()
        )

        numeric_count = sum(
            1
            for data_type in self.data_types.values()
            if data_type == DataType.NUMERIC
        )

        categorical_count = sum(
            1
            for data_type in self.data_types.values()
            if data_type == DataType.CATEGORICAL
        )

        logger.debug(
            "初始化适配器",
            adapter=self.__class__.__name__,
            feature_count=len(
                self.feature_names or []
            ),
            numeric_count=numeric_count,
            categorical_count=categorical_count,
            capabilities=int(
                self.capabilities
            ),
        )

    def _detect_capabilities(
            self,
    ) -> ModelCapability:
        """检测当前模型实例能力

        默认返回类级别静态能力声明。

        子类可覆盖此方法，根据实际模型实例动态检测能力。

        返回：
            模型能力位掩码
        """
        return self.SUPPORTED_CAPABILITIES

    @abstractmethod
    def predict_proba(
            self,
            X: np.ndarray,
    ) -> float:
        """预测违约概率

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            违约概率，范围 0 到 1
        """
        raise NotImplementedError

    @abstractmethod
    def decision_function(
            self,
            X: np.ndarray,
    ) -> float:
        """获取原始 Logit 值

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            Logit 值
        """
        raise NotImplementedError

    def predict_proba_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """批量概率预测

        支持向量化预测的模型适配器应重写此方法。

        默认逐条调用 predict_proba。

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            概率列表
        """
        logger.debug(
            "使用批量概率预测回退方案",
            sample_count=len(X),
        )

        return [
            self.predict_proba(
                row.reshape(1, -1)
            )
            for row in X
        ]

    def decision_function_batch(
            self,
            X: np.ndarray,
    ) -> list[float]:
        """批量获取原始 Logit 值

        支持向量化预测的模型适配器应重写此方法。

        默认逐条调用 decision_function。

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            Logit 值列表
        """
        logger.debug(
            "使用批量 Logit 预测回退方案",
            sample_count=len(X),
        )

        return [
            self.decision_function(
                row.reshape(1, -1)
            )
            for row in X
        ]

    def predict(
            self,
            X: np.ndarray
               | dict[str, Any]
               | list[dict[str, Any]],
    ) -> float | list[float]:
        """统一概率预测接口

        自动识别输入类型并执行单条或批量概率预测。

        参数：
            X: 输入数据，支持：
              - np.ndarray
              - dict[str, Any]
              - list[dict[str, Any]]

        返回：
            单条概率或概率列表

        异常：
            ValueError: 输入为空或数组维度错误
            TypeError: 输入类型不支持
            NotImplementedError: 当前模型不支持概率预测
        """
        if X is None:
            raise ValueError(
                "输入不能为 None"
            )

        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        if (
                isinstance(X, list)
                and len(X) == 0
        ):
            return []

        if (
                isinstance(X, np.ndarray)
                and X.size == 0
        ):
            return []

        if isinstance(
                X,
                dict,
        ):
            self.validate_features(X)

            return self.predict_proba(
                self.to_array(X)
            )

        if (
                isinstance(X, list)
                and X
                and isinstance(X[0], dict)
        ):
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

            raise ValueError(
                "仅支持 1D / 2D numpy 输入，"
                f"当前 ndim={X.ndim}"
            )

        raise TypeError(
            f"不支持类型: {type(X)}"
        )

    def predict_logit(
            self,
            X: np.ndarray
               | dict[str, Any]
               | list[dict[str, Any]],
    ) -> float | list[float]:
        """统一 Logit 预测接口

        自动识别输入类型并执行单条或批量 Logit 预测。

        参数：
            X: 输入数据，支持：
              - np.ndarray
              - dict[str, Any]
              - list[dict[str, Any]]

        返回：
            单条 Logit 或 Logit 列表

        异常：
            ValueError: 输入为空或数组维度错误
            TypeError: 输入类型不支持
            NotImplementedError: 当前模型不支持 Logit 输出
        """
        if X is None:
            raise ValueError(
                "输入不能为 None"
            )

        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        if (
                isinstance(X, list)
                and len(X) == 0
        ):
            return []

        if (
                isinstance(X, np.ndarray)
                and X.size == 0
        ):
            return []

        if isinstance(
                X,
                dict,
        ):
            self.validate_features(X)

            return self.decision_function(
                self.to_array(X)
            )

        if (
                isinstance(X, list)
                and X
                and isinstance(X[0], dict)
        ):
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

            raise ValueError(
                "仅支持 1D / 2D numpy 输入，"
                f"当前 ndim={X.ndim}"
            )

        raise TypeError(
            f"不支持类型: {type(X)}"
        )

    def to_array(
            self,
            features: dict[str, Any],
    ) -> np.ndarray:
        """特征字典转 numpy 数组

        转换规则：
          - 数值特征：转换为浮点数
          - 布尔特征：转换为 0.0 或 1.0
          - 字符串：保留原值
          - 缺失特征：填充 np.nan

        参数：
            features: 特征字典

        返回：
            numpy 数组，形状为 (1, n_features)

        异常：
            ValueError:
                特征字典为空
                feature_names 为空
        """
        if not features:
            raise ValueError(
                "features 不能为空"
            )

        if not self.feature_names:
            raise ValueError(
                "feature_names 不能为空"
            )

        feature_index = (
            self._get_feature_index()
        )

        values = [
            np.nan
            for _ in self.feature_names
        ]

        for name, value in features.items():
            idx = feature_index.get(
                name
            )

            if idx is not None:
                values[idx] = (
                    self._to_value_or_nan(
                        value,
                        name,
                    )
                )

        return np.array(
            [values],
            dtype=object,
        )

    def to_array_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> np.ndarray:
        """批量特征字典转 numpy 数组

        参数：
            features_list: 特征字典列表

        返回：
            numpy 数组，形状为
            (n_samples, n_features)

        异常：
            ValueError: 特征列表为空
        """
        if not features_list:
            raise ValueError(
                "features_list 不能为空"
            )

        try:
            import pandas as pd

            df = pd.DataFrame(
                features_list
            )

            if self.feature_names:
                for column in self.feature_names:
                    if column not in df.columns:
                        df[column] = np.nan

                df = df[
                    self.feature_names
                ]

            else:
                df = df[
                    sorted(df.columns)
                ]

            return df.values.astype(
                object
            )

        except ImportError:
            logger.debug(
                "pandas 不可用，"
                "使用批量转换回退方案"
            )

            return (
                self._to_array_batch_fallback(
                    features_list
                )
            )

    def _to_array_batch_fallback(
            self,
            features_list: list[dict[str, Any]],
    ) -> np.ndarray:
        """批量特征转换回退实现

        参数：
            features_list: 特征字典列表

        返回：
            numpy 数组

        异常：
            ValueError:
                feature_names 为空
        """
        if not self.feature_names:
            raise ValueError(
                "feature_names 不能为空"
            )

        feature_index = (
            self._get_feature_index()
        )

        sample_count = len(
            features_list
        )

        feature_count = len(
            self.feature_names
        )

        arr = np.full(
            (
                sample_count,
                feature_count,
            ),
            np.nan,
            dtype=object,
        )

        for row_idx, features in enumerate(
                features_list
        ):
            for name, value in features.items():
                column_idx = (
                    feature_index.get(
                        name
                    )
                )

                if column_idx is not None:
                    arr[
                        row_idx,
                        column_idx,
                    ] = self._to_value_or_nan(
                        value,
                        name,
                    )

        return arr

    def _get_feature_index(
            self,
    ) -> dict[str, int]:
        """获取特征索引映射

        当索引尚未创建时，根据 feature_names
        延迟构建索引。

        返回：
            特征名称到位置的映射

        异常：
            ValueError: feature_names 为空
        """
        feature_index = self._feature_index

        if feature_index is not None:
            return feature_index

        if not self.feature_names:
            raise ValueError(
                "feature_names 不能为空"
            )

        feature_index = {
            name: idx
            for idx, name in enumerate(
                self.feature_names
            )
        }

        self._feature_index = feature_index

        return feature_index

    @staticmethod
    def _to_value_or_nan(
            value: Any,
            feature_name: str | None = None,
    ) -> Any:
        """将输入值转换为模型输入值

        规则：
          - None -> np.nan
          - bool -> 0.0 / 1.0
          - 数值 -> float
          - str -> 原值
          - 其他类型 -> 原值

        参数：
            value: 输入值
            feature_name: 特征名称

        返回：
            转换后的值
        """
        if value is None:
            return np.nan

        if isinstance(
                value,
                bool,
        ):
            return (
                1.0
                if value
                else 0.0
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
            return float(value)

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
            value=value,
        )

        return value

    def validate_features(
            self,
            features: dict[str, Any],
    ) -> tuple[
        list[str],
        list[tuple[str, str, str]],
    ]:
        """验证特征完整性和类型

        参数：
            features: 特征字典

        返回：
            二元组：
              - 缺失特征列表
              - 类型错误列表

            类型错误格式：
              (特征名, 期望类型, 实际类型)
        """
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
                if not isinstance(
                        value,
                        (
                                int,
                                float,
                                np.number,
                        ),
                ):
                    type_errors.append(
                        (
                            name,
                            "numeric",
                            type(
                                value
                            ).__name__,
                        )
                    )

            elif data_type == DataType.BOOLEAN:
                if not isinstance(
                        value,
                        (
                                bool,
                                int,
                                float,
                        ),
                ):
                    type_errors.append(
                        (
                            name,
                            "boolean",
                            type(
                                value
                            ).__name__,
                        )
                    )

        return (
            missing,
            type_errors,
        )

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取当前模型实例能力集

        返回：
            模型能力位掩码
        """
        return self.capabilities

    def has_capability(
            self,
            capability: ModelCapability,
    ) -> bool:
        """检查模型是否支持指定能力

        参数：
            capability: 模型能力

        返回：
            支持返回 True，否则返回 False
        """
        return bool(
            self.capabilities
            & capability
        )

    def require_capability(
            self,
            capability: ModelCapability,
    ) -> None:
        """校验模型能力

        参数：
            capability: 所需能力

        异常：
            NotImplementedError:
                当前模型不支持指定能力
        """
        if not self.has_capability(
                capability
        ):
            raise NotImplementedError(
                f"{self.__class__.__name__} "
                f"不支持能力: {capability.name}"
            )

    def get_feature_importance(
            self,
    ) -> dict[str, float]:
        """获取特征重要性

        返回：
            特征重要性字典

        异常：
            NotImplementedError:
                当前模型不支持特征重要性
                子类未实现特征重要性
        """
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        raise NotImplementedError(
            f"{self.__class__.__name__} "
            "未实现特征重要性"
        )
