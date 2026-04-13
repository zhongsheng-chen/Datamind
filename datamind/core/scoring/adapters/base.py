# datamind/core/scoring/adapters/base.py

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
  - get_feature_importance: 获取特征重要性（子类可重写）
  - get_capabilities: 获取模型能力集（子类可重写）
  - get_coef: 获取特征系数（仅逻辑回归模型）
  - get_intercept: 获取截距项（仅逻辑回归模型）
  - get_feature_logit: 获取特征对 logit 的贡献（仅逻辑回归模型）

特性：
  - 统一接口：所有框架模型通过相同方式调用
  - 类型自动识别：无需手动转换输入格式
  - 特征顺序保证：支持指定特征名列表，确保数组顺序与训练时一致
  - 缺失值保留：None 转换为 NaN，由 WOETransformer 处理
  - 分类型保留：字符串等分类特征保持原值，不强制转 float
  - 批量优化：子类可重写 predict_proba_batch 实现向量化计算
  - 易于扩展：新增框架只需继承并实现 predict_proba 和 decision_function
  - 能力驱动：支持模型能力声明和运行时检查
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Tuple

from datamind.core.logging import get_logger
from datamind.core.domain.enums import DataType

_logger = get_logger(__name__)


class BaseModelAdapter(ABC):
    """统一模型接口 - 所有框架适配器的基类"""

    def __init__(
        self,
        model,
        feature_names: Optional[List[str]] = None,
        data_types: Optional[Dict[str, DataType]] = None,
    ):
        """
        初始化适配器

        参数:
            model: 训练好的模型
            feature_names: 特征名称列表，用于保证特征顺序
            data_types: 特征数据类型映射，用于类型验证
        """
        self.model = model
        self.feature_names = feature_names
        self.data_types = data_types or {}

        # 预构建特征索引
        self._feature_index: Optional[Dict[str, int]] = None
        if feature_names:
            self._feature_index = {name: idx for idx, name in enumerate(feature_names)}

        # 记录特征类型分布
        numeric_count = sum(1 for dt in self.data_types.values() if dt == DataType.NUMERIC)
        categorical_count = sum(1 for dt in self.data_types.values() if dt == DataType.CATEGORICAL)
        _logger.debug("初始化适配器: %s, 特征数=%d, 数值型=%d, 分类型=%d",
                      self.__class__.__name__, len(self.feature_names or []), numeric_count, categorical_count)

    def get_model_id(self) -> str:
        """获取模型唯一标识（用于缓存）"""
        return str(id(self.model))

    # ==================== 核心抽象方法 ====================

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

    @abstractmethod
    def decision_function(self, X: np.ndarray) -> float:
        """
        获取原始 logit 值（核心方法，子类必须实现）

        这是评分卡 explain 的基础，子类必须直接调用模型的原始输出：
          - sklearn: model.decision_function(X)
          - XGBoost: model.predict(X, output_margin=True)
          - LightGBM: model.predict(X, raw_score=True)
          - CatBoost: model.predict(X, prediction_type='RawFormulaVal')

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            logit 值（原始模型输出）
        """
        pass

    # ==================== 批量方法 ====================

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率（子类可重写优化）

        默认实现为循环调用单条预测，效率较低。
        支持向量化的模型（sklearn、xgboost等）应重写此方法。

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        _logger.debug("使用默认循环批量预测，样本数: %d", len(X))
        return [self.predict_proba(x.reshape(1, -1)) for x in X]

    def decision_function_batch(self, X: np.ndarray) -> List[float]:
        """
        批量获取原始 logit 值（子类可重写优化）

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            logit 值列表
        """
        _logger.debug("使用默认循环批量获取 logit，样本数: %d", len(X))
        return [self.decision_function(x.reshape(1, -1)) for x in X]

    # ==================== 统一预测接口 ====================

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

        异常:
            ValueError: 输入类型不支持或数据为空
        """
        if X is None:
            raise ValueError("输入数据不能为 None")

        if isinstance(X, list) and len(X) == 0:
            _logger.warning("输入为空列表，返回空列表")
            return []

        if isinstance(X, np.ndarray) and X.size == 0:
            _logger.warning("输入为空数组，返回空列表")
            return []

        # 处理字典输入（单条）
        if isinstance(X, dict):
            missing, type_errors = self.validate_features(X)
            if missing:
                _logger.debug("缺失特征: %s，将转换为 NaN 由 WOE 处理", missing)
            if type_errors:
                _logger.warning("类型错误: %s", type_errors)

            X_array = self.to_array(X)
            return self.predict_proba(X_array)

        # 处理字典列表输入（批量）
        if isinstance(X, list) and X and isinstance(X[0], dict):
            if len(X) <= 100:
                for i, features in enumerate(X[:5]):
                    missing, type_errors = self.validate_features(features)
                    if missing:
                        _logger.debug("样本 %d 缺失特征: %s", i, missing)
                    if type_errors:
                        _logger.debug("样本 %d 类型错误: %s", i, type_errors)

            X_array = self.to_array_batch(X)
            return self.predict_proba_batch(X_array)

        # 处理数组输入
        if isinstance(X, np.ndarray):
            if X.ndim == 1:
                return self.predict_proba(X.reshape(1, -1))
            elif X.ndim == 2:
                return self.predict_proba_batch(X)
            else:
                raise ValueError(f"不支持的数组维度: {X.ndim}，仅支持 1D 或 2D")

        raise TypeError(f"不支持的类型: {type(X)}，支持的类型: np.ndarray, dict, List[dict]")

    def predict_logit(self, X: Union[np.ndarray, Dict[str, Any], List[Dict[str, Any]]]) -> Union[float, List[float]]:
        """
        预测 logit 值（原始模型输出）

        参数:
            X: 输入数据

        返回:
            logit 值或列表
        """
        if isinstance(X, dict):
            X_array = self.to_array(X)
            return self.decision_function(X_array)

        if isinstance(X, list) and X and isinstance(X[0], dict):
            X_array = self.to_array_batch(X)
            return self.decision_function_batch(X_array)

        if isinstance(X, np.ndarray):
            if X.ndim == 1:
                return self.decision_function(X.reshape(1, -1))
            elif X.ndim == 2:
                return self.decision_function_batch(X)

        raise TypeError(f"不支持的类型: {type(X)}")

    # ==================== 特征转换（保留分类型） ====================

    def to_array(self, features: Dict[str, Any]) -> np.ndarray:
        """
        特征字典转 numpy 数组（保留分类型为 object dtype）

        数值特征 -> float
        分类特征 -> 原始值（如字符串）
        缺失值 -> NaN

        参数:
            features: 特征字典

        返回:
            numpy 数组，形状为 (1, n_features)，dtype=object（混合类型）

        异常:
            ValueError: 特征字典为空
        """
        if not features:
            raise ValueError("特征字典不能为空")

        if self._feature_index is not None:
            # 使用预构建索引（性能优化）
            values = [np.nan] * len(self.feature_names)
            for name, value in features.items():
                idx = self._feature_index.get(name)
                if idx is not None:
                    values[idx] = self._to_value_or_nan(value, name)
        else:
            # 降级：按特征名排序
            values = []
            for name in sorted(features.keys()):
                values.append(self._to_value_or_nan(features[name], name))

        # 使用 object dtype 以支持混合类型（数值 + 字符串）
        return np.array([values], dtype=object)

    def to_array_batch(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """
        批量特征字典转 numpy 数组（保留分类型为 object dtype）

        参数:
            features_list: 特征字典列表

        返回:
            numpy 数组，形状为 (n_samples, n_features)，dtype=object

        异常:
            ValueError: 特征列表为空
        """
        if not features_list:
            raise ValueError("特征列表不能为空")

        try:
            import pandas as pd
            return self._to_array_batch_pandas(features_list)
        except ImportError:
            _logger.debug("pandas 不可用，使用原生实现")
            return self._to_array_batch_fallback(features_list)
        except Exception as e:
            _logger.error("批量转换失败: %s", e)
            raise

    def _to_array_batch_pandas(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """使用 pandas 实现批量特征转换（保留分类型）"""
        import pandas as pd

        df = pd.DataFrame(features_list)

        if self.feature_names:
            # 确保所有特征列都存在，缺失的填充 NaN
            for col in self.feature_names:
                if col not in df.columns:
                    df[col] = np.nan
            df = df[self.feature_names]
        else:
            df = df[sorted(df.columns)]

        # 注意：不转换类型，保留原始值（字符串等）
        # 数值列会自动成为 float，字符串列保持 object
        return df.values.astype(object)

    def _to_array_batch_fallback(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """回退方案：原生实现批量特征转换"""
        if self._feature_index is not None:
            n_features = len(self.feature_names)
            # 使用 object dtype 初始化
            values = np.full((len(features_list), n_features), np.nan, dtype=object)

            for i, features in enumerate(features_list):
                for name, value in features.items():
                    idx = self._feature_index.get(name)
                    if idx is not None:
                        values[i, idx] = self._to_value_or_nan(value, name)
            return values
        else:
            # 动态收集所有特征名
            all_keys = sorted({k for features in features_list for k in features.keys()})
            values = np.full((len(features_list), len(all_keys)), np.nan, dtype=object)

            for i, features in enumerate(features_list):
                for j, key in enumerate(all_keys):
                    value = features.get(key)
                    values[i, j] = self._to_value_or_nan(value, key)
            return values

    @staticmethod
    def _to_value_or_nan(value: Any, feature_name: Optional[str] = None) -> Any:
        """
        将值转换为合适的类型，无法转换时返回 NaN

        规则：
          - None -> np.nan
          - 数值类型 -> float
          - 布尔类型 -> float (0.0/1.0)
          - 字符串 -> 保留原值（分类型，由 WOETransformer 处理）
          - 其他类型 -> 保留原值或 NaN

        参数:
            value: 输入值
            feature_name: 特征名称（用于日志）

        返回:
            转换后的值，或 np.nan
        """
        # 缺失值 -> NaN
        if value is None:
            return np.nan

        # 数值类型 -> float
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, (np.integer, np.floating)):
            return float(value)

        # 布尔类型 -> 0.0/1.0
        if isinstance(value, bool):
            return 1.0 if value else 0.0

        # 字符串 -> 保留原值（分类型，由 WOETransformer 处理）
        if isinstance(value, str):
            return value

        # 其他类型：记录警告，尝试保留原值
        _logger.debug("特征 '%s' 的类型 %s 将保留原值: %s",
                      feature_name, type(value).__name__, value)
        return value

    # ==================== 特征验证 ====================

    def validate_features(self, features: Dict[str, Any]) -> Tuple[List[str], List[Tuple[str, str, str]]]:
        """
        验证特征完整性和类型

        参数:
            features: 特征字典

        返回:
            (缺失特征列表, 类型错误列表)
            类型错误格式: (特征名, 期望类型, 实际类型)
        """
        missing = []
        type_errors = []

        if not self.feature_names:
            return missing, type_errors

        for name in self.feature_names:
            value = features.get(name)

            if value is None:
                missing.append(name)
                continue

            expected_type = self.data_types.get(name, DataType.ANY)

            if expected_type == DataType.ANY:
                continue

            if expected_type == DataType.NUMERIC:
                if not isinstance(value, (int, float, np.integer, np.floating)):
                    type_errors.append((name, expected_type.value, type(value).__name__))

            elif expected_type == DataType.BOOLEAN:
                if not isinstance(value, bool):
                    if not isinstance(value, (int, float, np.integer, np.floating)) or value not in (0, 1):
                        type_errors.append((name, expected_type.value, type(value).__name__))

            elif expected_type == DataType.CATEGORICAL:
                # 分类特征可以是字符串、整数等，不做严格类型检查
                pass

        if missing:
            _logger.debug("缺失特征: %s", missing)

        if type_errors:
            _logger.warning("类型错误: %s", type_errors)

        return missing, type_errors

    # ==================== 模型能力 ====================

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        子类可重写此方法以提供特征重要性提取功能。

        返回:
            特征重要性字典

        异常:
            NotImplementedError: 子类未实现
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 不支持特征重要性提取"
        )

    def get_capabilities(self):
        """
        获取模型能力集

        子类应重写此方法返回具体能力。

        返回:
            ScorecardCapability 位掩码
        """
        from datamind.core.scoring.capability import ScorecardCapability
        return ScorecardCapability.NONE

    def get_coef(self, feature_name: str) -> float:
        """
        获取特征系数（仅逻辑回归模型）

        子类可重写此方法以提供系数提取功能。

        参数:
            feature_name: 特征名称

        返回:
            特征系数

        异常:
            NotImplementedError: 非逻辑回归模型
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 不支持系数提取，请检查模型类型是否为逻辑回归"
        )

    def get_intercept(self) -> float:
        """
        获取截距项（仅逻辑回归模型）

        子类可重写此方法以提供截距提取功能。

        返回:
            截距值

        异常:
            NotImplementedError: 非逻辑回归模型
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 不支持截距提取"
        )

    def get_feature_logit(self, feature_name: str, woe: float) -> float:
        """
        获取特征对 logit 的贡献（仅评分卡模型实现）

        对于逻辑回归模型，贡献 = coefficient × woe。

        参数:
            feature_name: 特征名称
            woe: 特征的 WOE 值

        返回:
            特征对 logit 的贡献值

        异常:
            NotImplementedError: 非评分卡模型
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 不支持 get_feature_logit，请检查是否为评分卡模型"
        )