# datamind/core/model/adapters/factory.py

"""模型适配器工厂

根据模型类所属模块识别机器学习框架，并创建对应适配器。

核心功能：
  - create: 创建模型适配器
  - get_framework: 获取模型所属框架
  - register_adapter: 注册模型适配器
  - get_adapter_class: 获取已注册的适配器类

使用示例：
  from sklearn.linear_model import LogisticRegression

  from datamind.constants import Framework
  from datamind.core.model.adapters.factory import ModelAdapterFactory

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
  )

  framework = ModelAdapterFactory.get_framework(
      model
  )

  adapter_class = ModelAdapterFactory.get_adapter_class(
      framework
  )

  ModelAdapterFactory.register_adapter(
      Framework.SKLEARN,
      adapter_class,
      override=True,
  )
"""

from typing import (
    Any,
    ClassVar,
)

from datamind.constants import (
    DataType,
    Framework,
)
from datamind.core.model.adapters.base import BaseModelAdapter
from datamind.core.model.adapters.catboost import CatBoostAdapter
from datamind.core.model.adapters.lightgbm import LightGBMAdapter
from datamind.core.model.adapters.sklearn import SklearnAdapter
from datamind.core.model.adapters.xgboost import XGBoostAdapter


class ModelAdapterFactory:
    """模型适配器工厂"""

    _ADAPTERS: ClassVar[
        dict[
            Framework,
            type[BaseModelAdapter],
        ]
    ] = {}

    @classmethod
    def create(
            cls,
            model: Any,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            positive_class: Any = 1,
    ) -> BaseModelAdapter:
        """创建模型适配器"""
        framework = cls.get_framework(
            model
        )

        adapter_class = cls.get_adapter_class(
            framework
        )

        return adapter_class(
            model=model,
            feature_names=feature_names,
            data_types=data_types,
            positive_class=positive_class,
        )

    @staticmethod
    def get_framework(
            model: Any,
    ) -> Framework:
        """获取模型所属框架"""
        if model is None:
            raise ValueError(
                "model 不能为空"
            )

        module_name = str(
            model.__class__.__module__
        ).lower()

        if module_name.startswith(
                "xgboost"
        ):
            return Framework.XGBOOST

        if module_name.startswith(
                "lightgbm"
        ):
            return Framework.LIGHTGBM

        if module_name.startswith(
                "catboost"
        ):
            return Framework.CATBOOST

        if (
                module_name == "sklearn"
                or module_name.startswith(
                    "sklearn."
                )
        ):
            return Framework.SKLEARN

        model_name = str(
            model.__class__.__name__
        )

        raise ValueError(
            "不支持的模型类型: "
            f"{model_name}"
        )

    @classmethod
    def register_adapter(
            cls,
            framework: Framework,
            adapter_class: type[BaseModelAdapter],
            *,
            override: bool = False,
    ) -> None:
        """注册模型适配器

        参数：
            framework: 机器学习框架
            adapter_class: 模型适配器类
            override: 是否覆盖已注册的适配器

        异常：
            TypeError: framework 或 adapter_class 类型不正确
            ValueError: 适配器已注册且不允许覆盖
        """
        if not isinstance(
                framework,
                Framework,
        ):
            raise TypeError(
                "framework 必须是 Framework 枚举"
            )

        if (
                not isinstance(
                    adapter_class,
                    type,
                )
                or not issubclass(
                    adapter_class,
                    BaseModelAdapter,
                )
        ):
            raise TypeError(
                "adapter_class 必须继承 "
                "BaseModelAdapter"
            )

        if (
                framework in cls._ADAPTERS
                and not override
        ):
            framework_name = str(
                framework
            )

            raise ValueError(
                "模型适配器已注册: "
                f"{framework_name}"
            )

        cls._ADAPTERS[
            framework
        ] = adapter_class

    @classmethod
    def get_adapter_class(
            cls,
            framework: Framework,
    ) -> type[BaseModelAdapter]:
        """获取已注册的适配器类"""
        adapter_class = cls._ADAPTERS.get(
            framework
        )

        if adapter_class is None:
            framework_name = str(
                framework
            )

            raise ValueError(
                "未注册模型适配器: "
                f"{framework_name}"
            )

        return adapter_class


ModelAdapterFactory.register_adapter(
    Framework.SKLEARN,
    SklearnAdapter,
)

ModelAdapterFactory.register_adapter(
    Framework.XGBOOST,
    XGBoostAdapter,
)

ModelAdapterFactory.register_adapter(
    Framework.LIGHTGBM,
    LightGBMAdapter,
)

ModelAdapterFactory.register_adapter(
    Framework.CATBOOST,
    CatBoostAdapter,
)
