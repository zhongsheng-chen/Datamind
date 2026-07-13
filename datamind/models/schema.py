# datamind/models/schema.py

"""Schema 提取器

从模型对象中提取输入 Schema。

核心功能：
  - extract: 提取模型输入 Schema

返回格式示例：
    {
          "feature_names": [
              "age",
              "annual_income",
              "debt_to_income_ratio",
              "credit_utilization_ratio",
              "delinquency_count"
        ],
          "data_types": {
              "age": "numeric",
              "annual_income": "numeric",
              "debt_to_income_ratio": "numeric",
              "credit_utilization_ratio": "numeric",
              "delinquency_count": "numeric"
        },
        "inferred": true,
        "source": "model.feature_names_in_"
    }

使用示例：
  from datamind.models.schema import SchemaExtractor

  schema = SchemaExtractor.extract(
      model=model,
      framework="sklearn"
  )

  if schema:
      print(schema["feature_names"])
"""

from collections.abc import Iterable
from operator import methodcaller
from typing import Any

from datamind.constants.data_type import DataType
from datamind.constants.framework import Framework


def _call_method(
        value: object,
        method_name: str,
        *,
        default: Any = None,
) -> Any:
    """调用对象的无参数方法"""
    method: object = getattr(
        value,
        method_name,
        None,
    )

    if not callable(method):
        return default

    return methodcaller(
        method_name
    )(value)


class SchemaExtractor:
    """Schema 提取器"""

    DEFAULT_DATA_TYPE = DataType.NUMERIC.value

    SOURCE_MAPPING = {
        Framework.SKLEARN: "model.feature_names_in_",
        Framework.XGBOOST: "model.feature_names",
        Framework.LIGHTGBM: "model.feature_name()",
        Framework.CATBOOST: "model.feature_names_",
    }

    @classmethod
    def extract(
            cls,
            *,
            model: Any,
            framework: str,
    ) -> dict | None:
        """提取模型输入 Schema

        参数：
            model: 模型对象
            framework: 模型框架

        返回：
            Schema 字典

        异常：
            KeyError: 不支持的框架
        """
        feature_names = cls._extract_feature_names(
            model=model,
            framework=framework,
        )

        if not feature_names:
            return None

        data_types = {
            feature_name: cls.DEFAULT_DATA_TYPE
            for feature_name in feature_names
        }

        return {
            "feature_names": feature_names,
            "data_types": data_types,
            "inferred": True,
            "source": cls._get_source(
                framework=framework,
                model=model,
            ),
        }

    @staticmethod
    def _extract_feature_names(
            *,
            model: Any,
            framework: str,
    ) -> list[str] | None:
        """提取特征名称

        参数：
            model: 模型对象
            framework: 模型框架

        返回：
            特征名称列表，如果无法提取则返回 None

        异常：
            KeyError: 不支持的框架
        """
        framework = framework.lower()

        if framework == Framework.SKLEARN:
            feature_names = getattr(
                model,
                "feature_names_in_",
                None,
            )

        elif framework == Framework.XGBOOST:
            feature_names = getattr(
                model,
                "feature_names_in_",
                None,
            )

            if feature_names is None:
                feature_names = getattr(
                    model,
                    "feature_names",
                    None,
                )

            if feature_names is None:
                booster_obj = _call_method(
                    model,
                    "get_booster",
                )

                if booster_obj is not None:
                    feature_names = getattr(
                        booster_obj,
                        "feature_names",
                        None,
                    )

        elif framework == Framework.LIGHTGBM:
            feature_names = getattr(
                model,
                "feature_name_",
                None,
            )

            if feature_names is None:
                feature_names = _call_method(
                    model,
                    "feature_name",
                )

            if feature_names is None:
                booster = getattr(
                    model,
                    "booster_",
                    None,
                )

                if booster is not None:
                    feature_names = _call_method(
                        booster,
                        "feature_name",
                    )

        elif framework == Framework.CATBOOST:
            feature_names = getattr(
                model,
                "feature_names_",
                None,
            )

        else:
            raise KeyError(f"不支持的框架: {framework}")

        if feature_names is None:
            return None

        feature_name_values = _call_method(
            feature_names,
            "tolist",
            default=feature_names,
        )

        if isinstance(feature_name_values, str):
            return [feature_name_values]

        if not isinstance(feature_name_values, Iterable):
            return None

        return [
            str(feature_name)
            for feature_name in feature_name_values
        ]

    @classmethod
    def _get_source(
            cls,
            *,
            framework: str,
            model: Any,
    ) -> str:
        """返回 Schema 来源

        参数：
            framework: 模型框架
            model: 模型对象

        返回：
            来源描述字符串

        异常：
            KeyError: 不支持的框架
        """
        framework_value = framework.lower()

        try:
            framework_enum = Framework(framework_value)
        except ValueError as exc:
            raise KeyError(
                f"不支持的框架: {framework_value}"
            ) from exc

        if framework_enum == Framework.XGBOOST:
            if getattr(model, "feature_names_in_", None) is not None:
                return "model.feature_names_in_"

            if getattr(model, "feature_names", None) is not None:
                return "model.feature_names"

            return "model.get_booster().feature_names"

        if framework_enum == Framework.LIGHTGBM:
            if getattr(model, "feature_name_", None) is not None:
                return "model.feature_name_"

            if callable(getattr(model, "feature_name", None)):
                return "model.feature_name()"

            return "model.booster_.feature_name()"

        try:
            return cls.SOURCE_MAPPING[framework_enum]
        except KeyError as exc:
            raise KeyError(
                f"不支持的框架: {framework_value}"
            ) from exc
