# datamind/core/model/adapters/base.py

"""基础模型适配器

提供统一的模型接口规范，所有框架适配器必须继承此类。

核心功能：
  - predict_proba: 预测违约概率（抽象方法，子类必须实现）
  - decision_function: 获取原始 logit 值（抽象方法，子类必须实现）
  - predict_proba_batch: 批量预测概率（子类可重写优化）
  - decision_function_batch: 批量获取 logit（子类可重写优化）
  - predict: 统一的预测接口，自动识别输入类型并分发
  - predict_logit: 统一的 logit 预测接口
  - to_array: 特征字典转 numpy 数组
  - to_array_batch: 批量特征字典转 numpy 数组
  - validate_features: 验证特征完整性和类型
  - get_feature_importance: 获取特征重要性（子类需实现）
  - get_capabilities: 获取模型能力集

使用示例：
    from datamind.core.model.adapters.base import BaseModelAdapter

    class CustomModel(BaseModelAdapter):
        ...

"""

import structlog
import numpy as np
from abc import ABC, abstractmethod
from typing import Any

from datamind.constants import DataType
from datamind.core.capability import ModelCapability

logger = structlog.get_logger(__name__)


class BaseModelAdapter(ABC):
    """统一模型接口

    所有框架适配器的基类

    属性：
        SUPPORTED_CAPABILITIES: 类级别能力声明，子类可覆盖
        model: 原始模型对象
        feature_names: 特征名称列表
        data_types: 特征数据类型映射
        capabilities: 实例能力集
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

        self.capabilities = self.SUPPORTED_CAPABILITIES

        self._feature_index = (
            {name: idx for idx, name in enumerate(feature_names)}
            if feature_names else None
        )

        numeric_count = sum(
            1 for dt in self.data_types.values()
            if dt == DataType.NUMERIC
        )
        categorical_count = sum(
            1 for dt in self.data_types.values()
            if dt == DataType.CATEGORICAL
        )

        logger.debug(
            "初始化适配器 | 类型=%s | 特征数=%d | 数值=%d | 分类=%d",
            self.__class__.__name__,
            len(self.feature_names or []),
            numeric_count,
            categorical_count,
        )

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> float:
        """预测违约概率（核心方法，子类必须实现）

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            违约概率 (0-1)
        """
        pass

    @abstractmethod
    def decision_function(self, X: np.ndarray) -> float:
        """获取原始 logit 值（核心方法，子类必须实现）

        返回未经概率转换的模型原始输出。

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            logit 值
        """
        pass

    def predict_proba_batch(self, X: np.ndarray) -> list[float]:
        """批量概率预测

        支持向量化的模型应重写此方法以提高性能。

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            概率列表，长度 n_samples
        """
        logger.debug("batch predict_proba fallback: %d", len(X))
        return [self.predict_proba(x.reshape(1, -1)) for x in X]

    def decision_function_batch(self, X: np.ndarray) -> list[float]:
        """批量获取 raw score

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            logit 值列表
        """
        logger.debug("batch decision_function fallback: %d", len(X))
        return [self.decision_function(x.reshape(1, -1)) for x in X]

    def predict(
        self,
        X: np.ndarray | dict[str, Any] | list[dict[str, Any]]
    ) -> float | list[float]:
        """统一的预测接口，自动识别输入类型并分发

        参数：
            X: 输入数据，支持以下格式:
                - np.ndarray: 特征数组，形状为 (1, n_features) 或 (n_samples, n_features)
                - dict[str, Any]: 单条特征字典
                - list[dict[str, Any]]: 多条特征字典列表

        返回：
            float 或 list[float]: 违约概率 (0-1)

        异常：
            ValueError: 输入数据为 None
            TypeError: 不支持的类型
        """
        if X is None:
            raise ValueError("输入不能为 None")

        if isinstance(X, list) and len(X) == 0:
            return []

        if isinstance(X, np.ndarray) and X.size == 0:
            return []

        if isinstance(X, dict):
            self.validate_features(X)
            return self.predict_proba(self.to_array(X))

        if isinstance(X, list) and X and isinstance(X[0], dict):
            return self.predict_proba_batch(self.to_array_batch(X))

        if isinstance(X, np.ndarray):
            if X.ndim == 1:
                return self.predict_proba(X.reshape(1, -1))
            if X.ndim == 2:
                return self.predict_proba_batch(X)
            raise ValueError(f"仅支持 1D / 2D numpy 输入，当前 ndim={X.ndim}")

        raise TypeError(f"不支持类型: {type(X)}")

    def predict_logit(
        self,
        X: np.ndarray | dict[str, Any] | list[dict[str, Any]]
    ) -> float | list[float]:
        """预测 logit 值

        logit 值，也是原始模型输出

        参数：
            X: 输入数据

        返回：
            float 或 list[float]: logit 值
        """
        if isinstance(X, dict):
            return self.decision_function(self.to_array(X))

        if isinstance(X, list) and X and isinstance(X[0], dict):
            return self.decision_function_batch(self.to_array_batch(X))

        if isinstance(X, np.ndarray):
            if X.ndim == 1:
                return self.decision_function(X.reshape(1, -1))
            if X.ndim == 2:
                return self.decision_function_batch(X)
            raise ValueError(f"仅支持 1D / 2D numpy 输入，当前 ndim={X.ndim}")

        raise TypeError(f"不支持类型: {type(X)}")

    def to_array(self, features: dict[str, Any]) -> np.ndarray:
        """特征字典转 numpy 数组

        转换规则：
            - 数值特征：保留为数值类型
            - 分类特征：保留原始取值（如字符串）
            - 缺失特征：填充为 NaN

        参数：
            features: 特征字典

        返回：
            numpy 数组，形状为 (1, n_features)，dtype=object

        异常：
            ValueError: 特征字典为空
        """
        if not features:
            raise ValueError("features 不能为空")

        if not self.feature_names:
            raise ValueError("feature_names 不能为空")

        values = [np.nan] * len(self.feature_names)

        for k, v in features.items():
            idx = self._feature_index.get(k)

            if idx is not None:
                values[idx] = self._to_value_or_nan(v, k)

        return np.array([values], dtype=object)

    def to_array_batch(self, features_list: list[dict[str, Any]]) -> np.ndarray:
        """批量特征字典转 numpy 数组

        参数：
            features_list: 特征字典列表

        返回：
            numpy 数组，形状为 (n_samples, n_features)，dtype=object

        异常：
            ValueError: 特征列表为空
        """
        if not features_list:
            raise ValueError("features_list 不能为空")

        try:
            import pandas as pd

            df = pd.DataFrame(features_list)

            if self.feature_names:
                for col in self.feature_names:
                    if col not in df.columns:
                        df[col] = np.nan
                df = df[self.feature_names]
            else:
                df = df[sorted(df.columns)]

            return df.values.astype(object)

        except ImportError:
            logger.debug("pandas 不可用 fallback")
            return self._to_array_batch_fallback(features_list)

    def _to_array_batch_fallback(self, features_list: list[dict[str, Any]]) -> np.ndarray:
        """回退方案：原生实现批量特征转换"""
        n = len(features_list)

        if not self.feature_names:
            raise ValueError("feature_names 不能为空")

        if self._feature_index:
            m = len(self.feature_names)
            arr = np.full((n, m), np.nan, dtype=object)

            for i, f in enumerate(features_list):
                for k, v in f.items():
                    idx = self._feature_index.get(k)
                    if idx is not None:
                        arr[i, idx] = self._to_value_or_nan(v, k)

            return arr

        keys = self.feature_names or sorted(
            {k for f in features_list for k in f}
        )
        arr = np.full((n, len(keys)), np.nan, dtype=object)

        for i, f in enumerate(features_list):
            for j, k in enumerate(keys):
                arr[i, j] = self._to_value_or_nan(f.get(k), k)

        return arr

    @staticmethod
    def _to_value_or_nan(value: Any, feature_name: str | None = None) -> Any:
        """将值转换为合适的类型，无法转换时返回 NaN

        规则：
          - None -> np.nan
          - 数值类型 -> float
          - 布尔类型 -> float (0.0/1.0)
          - 字符串 -> 保留原值
          - 其他类型 -> 保留原值

        参数：
            value: 输入值
            feature_name: 特征名称

        返回：
            转换后的值，或 np.nan
        """
        if value is None:
            return np.nan

        if isinstance(value, bool):
            return 1.0 if value else 0.0

        if isinstance(value, (int, float, np.integer, np.floating)):
            return float(value)

        if isinstance(value, str):
            return value

        logger.debug(
            "特征类型未标准化 | 特征=%s | 类型=%s | 值=%s",
            feature_name,
            type(value).__name__,
            value,
        )

        return value

    def validate_features(
        self,
        features: dict[str, Any]
    ) -> tuple[list[str], list[tuple[str, str, str]]]:
        """验证特征完整性和类型

        参数：
            features: 特征字典

        返回：
            (缺失特征列表, 类型错误列表)
            类型错误格式: (特征名, 期望类型, 实际类型)
        """
        missing: list[str] = []
        type_errors: list[tuple[str, str, str]] = []

        if not self.feature_names:
            return missing, type_errors

        for name in self.feature_names:
            v = features.get(name)

            if v is None:
                missing.append(name)
                continue

            dt = self.data_types.get(name, DataType.ANY)

            if dt == DataType.NUMERIC:
                if not isinstance(v, (int, float, np.number)):
                    type_errors.append((name, "numeric", type(v).__name__))

            elif dt == DataType.BOOLEAN:
                if not isinstance(v, (bool, int, float)):
                    type_errors.append((name, "boolean", type(v).__name__))

        return missing, type_errors

    def get_capabilities(self) -> ModelCapability:
        """获取模型能力集

        返回：
            ModelCapability 位掩码
        """
        return self.capabilities

    def has_capability(self, cap: ModelCapability) -> bool:
        """检查模型是否支持指定能力

        参数：
            cap: 模型能力

        返回：
            支持返回 True，否则返回 False
        """
        return bool(self.capabilities & cap)

    def require_capability(self, cap: ModelCapability) -> None:
        """校验模型能力

        参数：
            cap: 所需能力

        异常：
            NotImplementedError: 模型不支持该能力
        """
        if not self.has_capability(cap):
            raise NotImplementedError(
                f"{self.__class__.__name__} 不支持能力: {cap.name}"
            )

    def get_feature_importance(self) -> dict[str, float]:
        """获取特征重要性

        返回：
            特征重要性字典

        异常：
            NotImplementedError: 子类未实现该方法
        """
        self.require_capability(ModelCapability.FEATURE_IMPORTANCE)
        raise NotImplementedError(
            f"{self.__class__.__name__} 未实现特征重要性"
        )