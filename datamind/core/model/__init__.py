# datamind/core/model/__init__.py

"""模型核心模块

提供多种机器学习框架的统一模型适配能力。

核心功能：
  - BaseModelAdapter: 模型适配器抽象基类
  - ModelAdapterFactory: 模型适配器工厂
  - SklearnAdapter: Scikit-learn 模型适配器
  - XGBoostAdapter: XGBoost 模型适配器
  - LightGBMAdapter: LightGBM 模型适配器
  - CatBoostAdapter: CatBoost 模型适配器

使用示例：
  from datamind.core.model import ModelAdapterFactory

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

from datamind.core.model.adapters import (
    BaseModelAdapter,
    CatBoostAdapter,
    LightGBMAdapter,
    ModelAdapterFactory,
    SklearnAdapter,
    XGBoostAdapter,
)


__all__ = [
    "BaseModelAdapter",
    "ModelAdapterFactory",
    "SklearnAdapter",
    "XGBoostAdapter",
    "LightGBMAdapter",
    "CatBoostAdapter",
]
