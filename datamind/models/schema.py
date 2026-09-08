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

from collections.abc import (
    Callable,
    Iterable,
)
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
        try:
            framework_enum = Framework(framework.lower())
        except ValueError as exc:
            raise KeyError(
                f"不支持的框架: {framework.lower()}"
            ) from exc

        extractors: dict[
            Framework,
            Callable[[Any], dict | None],
        ] = {
            Framework.SKLEARN: cls._extract_sklearn,
            Framework.XGBOOST: cls._extract_xgboost,
            Framework.LIGHTGBM: cls._extract_lightgbm,
            Framework.CATBOOST: cls._extract_catboost,
        }
        return extractors[framework_enum](model)

    @classmethod
    def _extract_sklearn(
            cls,
            model: Any,
    ) -> dict | None:
        """提取 sklearn 模型 Schema"""
        binning_process = getattr(model, "binning_process_", None)

        if binning_process is not None:
            feature_names = cls._normalize_feature_names(
                getattr(binning_process, "variable_names", None)
            )

            if not feature_names:
                return None

            categorical_features = {
                str(name)
                for name in (
                    getattr(
                        binning_process,
                        "categorical_variables",
                        None,
                    ) or []
                )
            }
            data_types = {
                name: (
                    DataType.CATEGORICAL.value
                    if name in categorical_features
                    else DataType.NUMERIC.value
                )
                for name in feature_names
            }
            return cls._build_schema(
                feature_names=feature_names,
                data_types=data_types,
                source="model.binning_process_",
            )

        return cls._build_schema(
            feature_names=cls._normalize_feature_names(
                getattr(model, "feature_names_in_", None)
            ),
            source="model.feature_names_in_",
        )

    @classmethod
    def _extract_xgboost(
            cls,
            model: Any,
    ) -> dict | None:
        """提取 XGBoost 模型 Schema"""
        schema = cls._build_first_available([
            (
                getattr(model, "feature_names_in_", None),
                "model.feature_names_in_",
            ),
            (
                getattr(model, "feature_names", None),
                "model.feature_names",
            ),
        ])

        if schema is not None:
            return schema

        booster = _call_method(model, "get_booster")

        return cls._build_schema(
            feature_names=cls._normalize_feature_names(
                getattr(booster, "feature_names", None)
            ),
            source="model.get_booster().feature_names",
        )

    @classmethod
    def _extract_lightgbm(
            cls,
            model: Any,
    ) -> dict | None:
        """提取 LightGBM 模型 Schema"""
        schema = cls._build_first_available([
            (
                getattr(model, "feature_names_in_", None),
                "model.feature_names_in_",
            ),
            (
                getattr(model, "feature_name_", None),
                "model.feature_name_",
            ),
        ])

        if schema is not None:
            return schema

        schema = cls._build_schema(
            feature_names=cls._normalize_feature_names(
                _call_method(model, "feature_name")
            ),
            source="model.feature_name()",
        )

        if schema is not None:
            return schema

        booster = getattr(model, "booster_", None)
        return cls._build_schema(
            feature_names=cls._normalize_feature_names(
                _call_method(booster, "feature_name")
            ),
            source="model.booster_.feature_name()",
        )

    @classmethod
    def _extract_catboost(
            cls,
            model: Any,
    ) -> dict | None:
        """提取 CatBoost 模型 Schema"""
        return cls._build_schema(
            feature_names=cls._normalize_feature_names(
                getattr(model, "feature_names_", None)
            ),
            source="model.feature_names_",
        )

    @classmethod
    def _build_first_available(
            cls,
            candidates: list[tuple[Any, str]],
    ) -> dict | None:
        """使用第一个有效的特征名称来源构造 Schema"""
        for value, source in candidates:
            feature_names = cls._normalize_feature_names(value)

            if feature_names:
                return cls._build_schema(
                    feature_names=feature_names,
                    source=source,
                )

        return None

    @classmethod
    def _build_schema(
            cls,
            *,
            feature_names: list[str] | None,
            source: str,
            data_types: dict[str, str] | None = None,
    ) -> dict | None:
        """构造统一的模型 Schema"""
        if not feature_names:
            return None

        return {
            "feature_names": feature_names,
            "data_types": data_types or {
                name: DataType.NUMERIC.value
                for name in feature_names
            },
            "inferred": True,
            "source": source,
        }

    @staticmethod
    def _normalize_feature_names(
            feature_names: Any,
    ) -> list[str] | None:
        """规范化模型提供的特征名称"""
        if feature_names is None:
            return None

        values = _call_method(
            feature_names,
            "tolist",
            default=feature_names,
        )

        if isinstance(values, str):
            return [values]

        if not isinstance(values, Iterable):
            return None

        names = [str(name) for name in values]
        return names or None
