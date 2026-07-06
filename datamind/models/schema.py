# datamind/models/schema.py

"""Schema 提取器

从模型对象中提取输入 Schema。

核心功能：
  - extract: 提取模型输入 Schema

返回格式示例：
    {
        "feature_names": [
            "age",
            "income",
            "gender"
        ],
        "data_types": {
            "age": "numeric",
            "income": "numeric",
            "gender": "numeric"
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

from typing import Any

from datamind.constants.data_type import DataType
from datamind.constants.framework import Framework


class SchemaExtractor:
    """Schema 提取器"""

    DEFAULT_DATA_TYPE = DataType.NUMERIC.value

    SOURCE_MAPPING = {
        Framework.sklearn: "model.feature_names_in_",
        Framework.xgboost: "model.feature_names_in_",
        Framework.lightgbm: "model.feature_name_",
        Framework.catboost: "model.feature_names_",
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
            "source": cls._get_source(framework),
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

        if framework == Framework.sklearn:
            feature_names = getattr(
                model,
                "feature_names_in_",
                None,
            )

        elif framework == Framework.xgboost:
            feature_names = getattr(
                model,
                "feature_names_in_",
                None,
            )

            if feature_names is None:
                booster = getattr(
                    model,
                    "get_booster",
                    None,
                )

                if callable(booster):
                    booster_obj = booster()

                    feature_names = getattr(
                        booster_obj,
                        "feature_names",
                        None,
                    )

        elif framework == Framework.lightgbm:
            feature_names = getattr(
                model,
                "feature_name_",
                None,
            )

            if feature_names is None:
                booster = getattr(
                    model,
                    "booster_",
                    None,
                )

                if booster is not None:
                    feature_name_fn = getattr(
                        booster,
                        "feature_name",
                        None,
                    )

                    if callable(feature_name_fn):
                        feature_names = feature_name_fn()
                    else:
                        feature_names = None

        elif framework == Framework.catboost:
            feature_names = getattr(
                model,
                "feature_names_",
                None,
            )

        else:
            raise KeyError(f"不支持的框架: {framework}")

        if feature_names is None:
            return None

        try:
            feature_names = feature_names.tolist()
        except AttributeError:
            feature_names = list(feature_names)

        return feature_names

    @classmethod
    def _get_source(
            cls,
            framework: str,
    ) -> str:
        """返回 Schema 来源

        参数：
            framework: 模型框架

        返回：
            来源描述字符串

        异常：
            KeyError: 不支持的框架
        """
        framework = framework.lower()

        try:
            return cls.SOURCE_MAPPING[framework]
        except KeyError:
            raise KeyError(f"不支持的框架: {framework}")
