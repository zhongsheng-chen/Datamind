# datamind/core/ml/common/adapters/base.py

"""基础模型适配器

提供统一的模型接口规范，所有框架适配器必须继承此类。

核心功能：
  - predict_proba: 预测违约概率（抽象方法，子类必须实现）
  - predict_proba_batch: 批量预测概率（子类可重写优化）
  - predict: 统一的预测接口，自动识别输入类型并分发
  - to_array: 特征字典转 numpy 数组
  - to_array_batch: 批量特征字典转 numpy 数组
  - get_feature_importance: 获取特征重要性（子类可重写）

特性：
  - 统一接口：所有框架模型通过相同方式调用
  - 类型自动识别：无需手动转换输入格式
  - 特征顺序保证：支持指定特征名列表，确保数组顺序与训练时一致
  - 批量优化：子类可重写 predict_proba_batch 实现向量化计算
  - 易于扩展：新增框架只需继承并实现 predict_proba 方法
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import Dict, Any, List, Optional, Union

from datamind.core.logging.debug import debug_print


class BaseModelAdapter(ABC):
    """统一模型接口 - 所有框架适配器的基类"""

    def __init__(self, model, feature_names: Optional[List[str]] = None):
        """
        初始化适配器

        参数:
            model: 训练好的模型
            feature_names: 特征名称列表（用于保证特征顺序）
        """
        self.model = model
        self.feature_names = feature_names
        debug_print(self.__class__.__name__, "初始化适配器")

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率（核心方法，子类必须实现）

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        pass

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率（子类可重写优化）

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        return [self.predict_proba(x.reshape(1, -1)) for x in X]

    def predict(self, X: Union[np.ndarray, Dict[str, Any], List[Dict[str, Any]]]) -> Union[float, List[float]]:
        """
        统一的预测接口，自动识别输入类型并分发

        参数:
            X: 输入数据，支持以下格式:
                - np.ndarray: 特征数组，形状为 (1, n_features) 或 (n_samples, n_features)
                - Dict[str, Any]: 单条特征字典，如 {"age": 35, "income": 50000}
                - List[Dict[str, Any]]: 多条特征字典列表

        返回:
            float 或 List[float]:
                - 单条输入返回违约概率 (0-1)
                - 批量输入返回概率列表

        示例:
            >>> adapter = SklearnAdapter(model)
            >>> # 数组输入
            >>> prob = adapter.predict(np.array([[35, 50000]]))
            >>> # 字典输入
            >>> prob = adapter.predict({"age": 35, "income": 50000})
            >>> # 批量字典输入
            >>> probs = adapter.predict([{"age": 35}, {"age": 28}])
        """
        # 处理字典输入（单条）
        if isinstance(X, dict):
            X_array = self.to_array(X)
            return self.predict_proba(X_array)

        # 处理字典列表输入（批量）
        if isinstance(X, list) and X and isinstance(X[0], dict):
            X_array = self.to_array_batch(X)
            return self.predict_proba_batch(X_array)

        # 处理数组输入
        if isinstance(X, np.ndarray):
            if X.ndim == 1:
                # 单条 1D 数组，转换为 (1, n_features)
                return self.predict_proba(X.reshape(1, -1))
            else:
                # 批量 2D 数组
                return self.predict_proba_batch(X)

        raise TypeError(f"不支持的类型: {type(X)}，支持的类型: np.ndarray, dict, List[dict]")

    def to_array(self, features: Dict[str, Any]) -> np.ndarray:
        """
        特征字典转 numpy 数组

        参数:
            features: 特征字典

        返回:
            numpy 数组，形状为 (1, n_features)
        """
        if self.feature_names:
            values = [features.get(name, 0) for name in self.feature_names]
        else:
            values = list(features.values())
        return np.array([values])

    def to_array_batch(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """
        批量特征字典转 numpy 数组

        参数:
            features_list: 特征字典列表

        返回:
            numpy 数组，形状为 (n_samples, n_features)
        """
        if not features_list:
            return np.array([])

        if self.feature_names:
            values = [
                [f.get(name, 0) for name in self.feature_names]
                for f in features_list
            ]
        else:
            values = [list(f.values()) for f in features_list]

        return np.array(values)

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        子类可重写此方法以提供特征重要性提取功能。

        返回:
            特征重要性字典，如 {"age": 0.35, "income": 0.42}，
            如果不支持则返回空字典
        """
        return {}