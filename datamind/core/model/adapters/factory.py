# datamind/core/model/adapters/factory.py

"""模型适配器工厂

根据模型类型自动创建对应的适配器。

核心功能：
    - create: 创建模型适配器
    - get_framework: 获取模型所属框架

使用示例：
    from datamind.core.model.adapters.factory import ModelAdapterFactory

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

    # 获取特征重要性
    importance = adapter.get_feature_importance()
"""

from datamind.core.model.adapters.sklearn import SklearnAdapter
from datamind.core.model.adapters.xgboost import XGBoostAdapter
from datamind.core.model.adapters.lightgbm import LightGBMAdapter
from datamind.core.model.adapters.catboost import CatBoostAdapter


class ModelAdapterFactory:
    """模型适配器工厂"""

    @staticmethod
    def create(
            model,
            feature_names=None,
            data_types=None,
    ):
        """创建模型适配器

        参数：
            model: 原始模型
            feature_names: 特征名称列表
            data_types: 特征类型映射

        返回：
            BaseModelAdapter

        异常：
            ValueError: 不支持的模型类型
        """
        framework = ModelAdapterFactory.get_framework(model)

        if framework == "xgboost":
            return XGBoostAdapter(
                model=model,
                feature_names=feature_names,
                data_types=data_types,
            )

        if framework == "lightgbm":
            return LightGBMAdapter(
                model=model,
                feature_names=feature_names,
                data_types=data_types,
            )

        if framework == "catboost":
            return CatBoostAdapter(
                model=model,
                feature_names=feature_names,
                data_types=data_types,
            )

        if framework == "sklearn":
            return SklearnAdapter(
                model=model,
                feature_names=feature_names,
                data_types=data_types,
            )

        raise ValueError(
            f"不支持的模型类型: {model.__class__.__name__}"
        )

    @staticmethod
    def get_framework(model) -> str:
        """获取模型所属框架

        参数：
            model: 原始模型

        返回：
            框架名称

        异常：
            ValueError: 不支持的模型类型
        """
        module_name = model.__class__.__module__

        if module_name.startswith("xgboost"):
            return "xgboost"

        if module_name.startswith("lightgbm"):
            return "lightgbm"

        if module_name.startswith("catboost"):
            return "catboost"

        if "sklearn" in module_name:
            return "sklearn"

        raise ValueError(
            f"不支持的模型类型: {model.__class__.__name__}"
        )