# datamind/core/inference/adapters/__init__.py

"""模型适配器模块

提供统一模型适配入口，支持模型框架识别和适配器创建。

核心功能：
  - BaseModelAdapter: 模型适配器抽象基类
  - ModelAdapterFactory: 模型适配器工厂
  - SklearnAdapter: Scikit-learn 模型适配器
  - XGBoostAdapter: XGBoost 模型适配器
  - LightGBMAdapter: LightGBM 模型适配器
  - CatBoostAdapter: CatBoost 模型适配器

使用示例：
  from datamind.core.inference.adapters import ModelAdapterFactory

  adapter = ModelAdapterFactory.create(
      model=trained_model,
      feature_names=[
          "age",
          "employment_type",
      ],
  )
"""

from datamind.core.inference.adapters.base import BaseModelAdapter
from datamind.core.inference.adapters.catboost import CatBoostAdapter
from datamind.core.inference.adapters.factory import ModelAdapterFactory
from datamind.core.inference.adapters.lightgbm import LightGBMAdapter
from datamind.core.inference.adapters.sklearn import SklearnAdapter
from datamind.core.inference.adapters.xgboost import XGBoostAdapter

__all__ = [
    "BaseModelAdapter",
    "SklearnAdapter",
    "XGBoostAdapter",
    "LightGBMAdapter",
    "CatBoostAdapter",
    "ModelAdapterFactory",
]
