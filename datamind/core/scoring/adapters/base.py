# datamind/core/scoring/adapters/base.py

"""基础模型适配器

提供统一的模型接口规范，所有框架适配器必须继承此类。

核心功能：
  - predict_proba: 预测违约概率（抽象方法，子类必须实现）
  - predict_proba_batch: 批量预测概率（子类可重写优化）
  - predict: 统一的预测接口，自动识别输入类型并分发
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
  - 批量优化：子类可重写 predict_proba_batch 实现向量化计算
  - 易于扩展：新增框架只需继承并实现 predict_proba 方法
  - 能力驱动：支持模型能力声明和运行时检查
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Tuple

from datamind.core.logging import get_logger
from datamind.core.domain.enums import DataType
from datamind.core.scoring.capability import ScorecardCapability

logger = get_logger(__name__)


class BaseModelAdapter(ABC):
    """统一模型接口 - 所有框架适配器的基类"""

    def __init__(
        self,
        model,
        feature_names: Optional[List[str]] = None,
        data_types: Optional[Dict[str, DataType]] = None,
        transformer: Optional[Any] = None
    ):
        """
        初始化适配器

        参数:
            model: 训练好的模型
            feature_names: 特征名称列表（用于保证特征顺序）
            data_types: 特征数据类型映射，用于类型验证
            transformer: WOE转换器（评分卡模型使用）
        """
        self.model = model
        self.feature_names = feature_names
        self.data_types = data_types or {}
        self.transformer = transformer

        logger.debug("初始化适配器: %s", self.__class__.__name__)

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

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率（子类可重写优化）

        默认实现为循环调用单条预测，效率较低。
        支持向量化的模型（sklearn、tensorflow、xgboost等）应重写此方法。

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        logger.debug("使用默认循环批量预测，样本数: %d", len(X))
        return [self.predict_proba(x.reshape(1, -1)) for x in X]

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
        # 处理空数据
        if X is None:
            raise ValueError("输入数据不能为 None")

        if isinstance(X, list) and len(X) == 0:
            logger.warning("输入为空列表，返回空列表")
            return []

        if isinstance(X, np.ndarray) and X.size == 0:
            logger.warning("输入为空数组，返回空列表")
            return []

        # 处理字典输入（单条）
        if isinstance(X, dict):
            missing, type_errors = self.validate_features_with_types(X)
            if missing:
                logger.debug("缺失特征: %s，将使用默认值 0", missing)
            if type_errors:
                logger.warning("类型错误: %s", type_errors)

            X_array = self.to_array(X)
            return self.predict_proba(X_array)

        # 处理字典列表输入（批量）
        if isinstance(X, list) and X and isinstance(X[0], dict):
            # 批量验证（仅对小批量验证，避免性能损耗）
            if len(X) <= 100:
                for i, features in enumerate(X[:5]):
                    missing, type_errors = self.validate_features_with_types(features)
                    if missing:
                        logger.debug("样本 %d 缺失特征: %s", i, missing)
                    if type_errors:
                        logger.debug("样本 %d 类型错误: %s", i, type_errors)

            X_array = self.to_array_batch(X)
            return self.predict_proba_batch(X_array)

        # 处理数组输入
        if isinstance(X, np.ndarray):
            if X.ndim == 1:
                # 单条 1D 数组，转换为 (1, n_features)
                return self.predict_proba(X.reshape(1, -1))
            elif X.ndim == 2:
                # 批量 2D 数组
                return self.predict_proba_batch(X)
            else:
                raise ValueError(f"不支持的数组维度: {X.ndim}，仅支持 1D 或 2D")

        raise TypeError(f"不支持的类型: {type(X)}，支持的类型: np.ndarray, dict, List[dict]")

    # ==================== 特征转换 ====================

    def to_array(self, features: Dict[str, Any]) -> np.ndarray:
        """
        特征字典转 numpy 数组

        参数:
            features: 特征字典

        返回:
            numpy 数组，形状为 (1, n_features)

        异常:
            ValueError: 特征值类型不支持
        """
        if not features:
            raise ValueError("特征字典不能为空")

        if self.feature_names:
            values = []
            for name in self.feature_names:
                value = features.get(name)
                if value is None:
                    logger.debug("特征 '%s' 缺失，使用默认值 0", name)
                    values.append(0.0)
                else:
                    values.append(self._to_float(value, name))
        else:
            values = []
            for k in sorted(features.keys()):
                values.append(self._to_float(features[k], k))

        return np.array([values], dtype=np.float32)

    def to_array_batch(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """
        批量特征字典转 numpy 数组

        参数:
            features_list: 特征字典列表

        返回:
            numpy 数组，形状为 (n_samples, n_features)

        异常:
            ValueError: 输入为空或特征值类型不支持
        """
        if not features_list:
            raise ValueError("特征列表不能为空")

        # 使用 pandas 提升性能（如果可用）
        try:
            import pandas as pd
            return self._to_array_batch_pandas(features_list)
        except ImportError:
            logger.debug("pandas 不可用，使用原生实现")
            return self._to_array_batch_fallback(features_list)
        except Exception as e:
            # 打印完整前几条样本，方便排查
            sample_count = min(3, len(features_list))
            logger.error("pandas 批量转换失败: %s", e)
            for i in range(sample_count):
                logger.error("  样本 %d: %s", i, features_list[i])
            raise

    def _to_array_batch_pandas(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """使用 pandas 实现批量特征转换"""
        import pandas as pd

        df = pd.DataFrame(features_list)

        if self.feature_names:
            missing = set(self.feature_names) - set(df.columns)
            if missing:
                logger.debug("缺失特征: %s，填充默认值 0", missing)

            for col in missing:
                df[col] = 0.0

            df = df[self.feature_names]
        else:
            df = df[sorted(df.columns)]

        df = df.fillna(0)
        return df.values.astype(np.float32)

    def _to_array_batch_fallback(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """回退方案：原生实现批量特征转换（pandas 不可用时使用）"""
        if self.feature_names:
            values = []
            for features in features_list:
                row = []
                for name in self.feature_names:
                    value = features.get(name, 0.0)
                    row.append(self._to_float(value, name))
                values.append(row)
        else:
            all_keys = sorted({k for features in features_list for k in features.keys()})
            values = []
            for features in features_list:
                row = [self._to_float(features.get(k, 0.0), k) for k in all_keys]
                values.append(row)

        return np.array(values, dtype=np.float32)

    @staticmethod
    def _to_float(value: Any, feature_name: Optional[str] = None) -> float:
        """
        将值转换为 float

        参数:
            value: 输入值
            feature_name: 特征名称（用于错误提示）

        返回:
            float 值

        异常:
            ValueError: 无法转换为 float
        """
        if value is None:
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, (np.integer, np.floating)):
            return float(value)

        if isinstance(value, bool):
            return 1.0 if value else 0.0

        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                if feature_name:
                    raise ValueError(f"特征 '{feature_name}' 的值 '{value}' 无法转换为 float")
                raise ValueError(f"无法将字符串 '{value}' 转换为 float")

        if feature_name:
            raise ValueError(f"特征 '{feature_name}' 不支持的类型: {type(value)}，值: {value}")
        raise ValueError(f"不支持的类型: {type(value)}，值: {value}")

    # ==================== 特征验证 ====================

    def validate_features(self, features: Dict[str, Any]) -> List[str]:
        """
        验证特征完整性

        参数:
            features: 特征字典

        返回:
            缺失的特征名称列表
        """
        if not self.feature_names:
            return []

        missing = [name for name in self.feature_names if name not in features]
        if missing:
            logger.debug("缺失特征: %s", missing)

        return missing

    def validate_features_with_types(self, features: Dict[str, Any]) -> Tuple[List[str], List[Tuple[str, str, str]]]:
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
            logger.debug("缺失特征: %s", missing)

        if type_errors:
            logger.warning("类型错误: %s", type_errors)

        return missing, type_errors

    # ==================== 模型能力 ====================

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        子类可重写此方法以提供特征重要性提取功能。

        返回:
            特征重要性字典，如果不支持则返回空字典
        """
        logger.debug("模型不支持特征重要性提取")
        return {}

    def get_capabilities(self) -> ScorecardCapability:
        """
        获取模型能力集

        子类应重写此方法返回具体能力。

        返回:
            ScorecardCapability 位掩码
        """
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
            NotImplementedError: 模型不支持系数提取
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
            NotImplementedError: 模型不支持截距提取
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
            NotImplementedError: 子类未实现此方法
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 不支持 get_feature_logit，请检查是否为评分卡模型"
        )