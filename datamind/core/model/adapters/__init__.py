# datamind/core/model/adapters/__init__.py

"""模型适配器模块

提供统一接口适配器，支持多种机器学习框架。

核心功能：
    - BaseModelAdapter: 适配器基类
    - SklearnAdapter: Sklearn 模型适配器
    - XGBoostAdapter: XGBoost 模型适配器
    - LightGBMAdapter: LightGBM 模型适配器
    - CatBoostAdapter: CatBoost 模型适配器
    - ModelAdapterFactory: 工厂类，自动创建适配器

使用示例：
    from datamind.core.model.adapters import ModelAdapterFactory

    # 创建适配器
    adapter = ModelAdapterFactory.create(
        model=model,
        feature_names=["age", "income", "credit_score"],
        data_types={"age": "numerical", "income": "numerical"},
    )

    # 预测概率
    proba = adapter.predict_proba(X)

    # 批量预测概率
    probas = adapter.predict_proba_batch(X_batch)

    # 获取 logit 值
    logit = adapter.decision_function(X)

    # 获取特征重要性
    importance = adapter.get_feature_importance()
"""

from .base import BaseModelAdapter
from .catboost import CatBoostAdapter
from .factory import ModelAdapterFactory
from .lightgbm import LightGBMAdapter
from .sklearn import SklearnAdapter
from .xgboost import XGBoostAdapter

__all__ = [
    "BaseModelAdapter",
    "SklearnAdapter",
    "XGBoostAdapter",
    "LightGBMAdapter",
    "CatBoostAdapter",
    "ModelAdapterFactory",
]
