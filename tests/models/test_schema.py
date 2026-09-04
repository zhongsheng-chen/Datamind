# tests/models/test_schema.py

"""模型 Schema 提取测试

验证各支持框架的特征名称提取、来源判定和异常边界。

核心功能：
  - test_extract_sklearn_schema:
    验证提取 Sklearn Schema
  - test_extract_xgboost_booster_schema:
    验证提取原生 XGBoost Booster Schema
  - test_extract_xgboost_estimator_booster_schema:
    验证通过 XGBoost 估计器的 Booster 提取 Schema
  - test_extract_lightgbm_booster_schema:
    验证提取原生 LightGBM Booster Schema
  - test_extract_lightgbm_estimator_booster_schema:
    验证通过 LightGBM 估计器的 Booster 提取 Schema
  - test_extract_catboost_schema:
    验证提取 CatBoost Schema
  - test_extract_feature_name_boundaries:
    验证数组式、空值和不可迭代特征名称
  - test_extract_rejects_unsupported_framework:
    验证拒绝不支持的框架
"""

from types import SimpleNamespace

import pytest

from datamind.constants.framework import Framework
from datamind.models.schema import SchemaExtractor


class ScorecardModel:
    """模拟 OptBinning Scorecard"""

    __module__ = "optbinning.scorecard.scorecard"

    def __init__(self) -> None:
        self.binning_process_ = SimpleNamespace(
            variable_names=[
                "age",
                "employment_type",
            ],
            categorical_variables=[
                "employment_type",
            ],
        )


def test_extract_sklearn_schema() -> None:
    """测试提取 Sklearn Schema 完整结构"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_names_in_=["age", "income"]
        ),
        framework="SKLEARN",
    )

    assert result == {
        "feature_names": ["age", "income"],
        "data_types": {
            "age": "numeric",
            "income": "numeric",
        },
        "inferred": True,
        "source": "model.feature_names_in_",
    }


def test_extract_optbinning_scorecard_schema() -> None:
    """测试从评分卡分箱过程提取特征类型"""
    result = SchemaExtractor.extract(
        model=ScorecardModel(),
        framework=str(Framework.SKLEARN),
    )

    assert result == {
        "feature_names": [
            "age",
            "employment_type",
        ],
        "data_types": {
            "age": "numeric",
            "employment_type": "categorical",
        },
        "inferred": True,
        "source": "model.binning_process_",
    }


def test_extract_xgboost_booster_schema() -> None:
    """测试提取原生 XGBoost Booster Schema"""
    model = SimpleNamespace(feature_names=["age", "income"])

    result = SchemaExtractor.extract(
        model=model,
        framework=str(Framework.XGBOOST),
    )

    assert result is not None
    assert result["feature_names"] == ["age", "income"]
    assert result["source"] == "model.feature_names"


def test_extract_xgboost_estimator_booster_schema() -> None:
    """测试通过 XGBoost 估计器的 Booster 提取 Schema"""
    booster = SimpleNamespace(
        feature_names=["age", "income"]
    )
    model = SimpleNamespace(
        get_booster=lambda: booster
    )

    result = SchemaExtractor.extract(
        model=model,
        framework=str(Framework.XGBOOST),
    )

    assert result is not None
    assert result["feature_names"] == ["age", "income"]
    assert result["source"] == "model.get_booster().feature_names"


def test_extract_lightgbm_booster_schema() -> None:
    """测试提取原生 LightGBM Booster Schema"""
    model = SimpleNamespace(feature_name=lambda: ["age", "income"])

    result = SchemaExtractor.extract(
        model=model,
        framework=str(Framework.LIGHTGBM),
    )

    assert result is not None
    assert result["feature_names"] == ["age", "income"]
    assert result["source"] == "model.feature_name()"


def test_extract_lightgbm_estimator_booster_schema() -> None:
    """测试通过 LightGBM 估计器的 Booster 提取 Schema"""
    booster = SimpleNamespace(
        feature_name=lambda: ["age", "income"]
    )
    model = SimpleNamespace(
        booster_=booster
    )

    result = SchemaExtractor.extract(
        model=model,
        framework=str(Framework.LIGHTGBM),
    )

    assert result is not None
    assert result["feature_names"] == ["age", "income"]
    assert result["source"] == "model.booster_.feature_name()"


def test_extract_prefers_lightgbm_feature_name_attribute() -> None:
    """测试优先使用 LightGBM 估计器的特征名称属性"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_name_=["preferred"],
            feature_name=lambda: ["fallback"],
            booster_=SimpleNamespace(
                feature_name=lambda: ["booster"]
            ),
        ),
        framework=str(Framework.LIGHTGBM),
    )

    assert result is not None
    assert result["feature_names"] == ["preferred"]
    assert result["source"] == "model.feature_name_"


def test_extract_prefers_lightgbm_sklearn_feature_names() -> None:
    """测试优先使用 LightGBM 的 sklearn 标准特征名称"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_names_in_=["preferred"],
            feature_name_=["fallback"],
        ),
        framework=str(Framework.LIGHTGBM),
    )

    assert result is not None
    assert result["feature_names"] == ["preferred"]
    assert result["source"] == "model.feature_names_in_"


def test_extract_catboost_schema() -> None:
    """测试提取 CatBoost Schema"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_names_=["age", "income"]
        ),
        framework=str(Framework.CATBOOST),
    )

    assert result is not None
    assert result["feature_names"] == ["age", "income"]
    assert result["source"] == "model.feature_names_"


def test_extract_prefers_estimator_feature_names() -> None:
    """测试优先使用估计器直接提供的特征名称"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_names_in_=["preferred"],
            feature_names=["fallback"],
            get_booster=lambda: SimpleNamespace(
                feature_names=["booster"]
            ),
        ),
        framework=str(Framework.XGBOOST),
    )

    assert result is not None
    assert result["feature_names"] == ["preferred"]
    assert result["source"] == "model.feature_names_in_"


def test_extract_rejects_unsupported_framework() -> None:
    """测试拒绝不支持的模型框架"""
    with pytest.raises(KeyError, match="不支持的框架"):
        SchemaExtractor.extract(
            model=SimpleNamespace(),
            framework="unsupported",
        )


def test_extract_supports_array_like_feature_names() -> None:
    """测试提取支持 tolist 的数组式特征名称"""
    feature_names = SimpleNamespace(
        tolist=lambda: ["age", 100]
    )

    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_names_in_=feature_names
        ),
        framework=str(Framework.SKLEARN),
    )

    assert result is not None
    assert result["feature_names"] == ["age", "100"]


def test_extract_supports_single_feature_name() -> None:
    """测试将单个字符串特征名称转换为列表"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_names_in_="age"
        ),
        framework=str(Framework.SKLEARN),
    )

    assert result is not None
    assert result["feature_names"] == ["age"]


def test_extract_ignores_non_iterable_feature_names() -> None:
    """测试忽略不可迭代的特征名称对象"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(feature_names_in_=object()),
        framework=str(Framework.SKLEARN),
    )

    assert result is None


@pytest.mark.parametrize(
    "framework",
    [
        Framework.XGBOOST,
        Framework.LIGHTGBM,
    ],
)
def test_extract_ignores_model_without_feature_names(
        framework: Framework,
) -> None:
    """测试忽略未提供特征名称的模型"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(),
        framework=str(framework),
    )

    assert result is None


@pytest.mark.parametrize(
    "feature_names",
    [
        None,
        [],
    ],
)
def test_extract_ignores_missing_or_empty_feature_names(
        feature_names: list[str] | None,
) -> None:
    """测试忽略缺失或空特征名称"""
    result = SchemaExtractor.extract(
        model=SimpleNamespace(
            feature_names_in_=feature_names
        ),
        framework=str(Framework.SKLEARN),
    )

    assert result is None
