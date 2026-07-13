# datamind/core/model/adapters/__init__.py

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
  from sklearn.linear_model import LogisticRegression

  from datamind.core.model.adapters import ModelAdapterFactory

  model = LogisticRegression()

  adapter = ModelAdapterFactory.create(
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
"""

from datamind.core.model.adapters.base import BaseModelAdapter
from datamind.core.model.adapters.catboost import CatBoostAdapter
from datamind.core.model.adapters.factory import ModelAdapterFactory
from datamind.core.model.adapters.lightgbm import LightGBMAdapter
from datamind.core.model.adapters.sklearn import SklearnAdapter
from datamind.core.model.adapters.xgboost import XGBoostAdapter

__all__ = [
    "BaseModelAdapter",
    "SklearnAdapter",
    "XGBoostAdapter",
    "LightGBMAdapter",
    "CatBoostAdapter",
    "ModelAdapterFactory",
]
