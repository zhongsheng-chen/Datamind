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

from importlib import import_module
from typing import TYPE_CHECKING, Any, Final

from datamind.core.inference.adapters.base import BaseModelAdapter
from datamind.core.inference.adapters.factory import ModelAdapterFactory

if TYPE_CHECKING:
    from datamind.core.inference.adapters.catboost import CatBoostAdapter
    from datamind.core.inference.adapters.lightgbm import LightGBMAdapter
    from datamind.core.inference.adapters.sklearn import SklearnAdapter
    from datamind.core.inference.adapters.xgboost import XGBoostAdapter


_ADAPTER_EXPORTS: Final[dict[str, str]] = {
    "SklearnAdapter": "datamind.core.inference.adapters.sklearn",
    "XGBoostAdapter": "datamind.core.inference.adapters.xgboost",
    "LightGBMAdapter": "datamind.core.inference.adapters.lightgbm",
    "CatBoostAdapter": "datamind.core.inference.adapters.catboost",
}

__all__ = [
    "BaseModelAdapter",
    "SklearnAdapter",
    "XGBoostAdapter",
    "LightGBMAdapter",
    "CatBoostAdapter",
    "ModelAdapterFactory",
]


def __getattr__(name: str) -> Any:
    """按需加载具体框架的模型适配器。"""
    module_name = _ADAPTER_EXPORTS.get(name)

    if module_name is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回包含延迟公共导出的模块属性列表。"""
    return sorted({*globals(), *__all__})
