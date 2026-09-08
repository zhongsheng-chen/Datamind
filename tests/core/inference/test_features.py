"""推理特征工具测试

验证特征名称规范化、模型矩阵构造、类型校验和数组维度处理。

核心功能：
  - test_feature_transformer_normalizes_names:
    验证规范化并复制特征名称
  - test_feature_transformer_rejects_invalid_names:
    验证拒绝空白或重复特征名称
  - test_to_feature_array_uses_configured_order:
    验证按照配置顺序构造单条特征矩阵
  - test_to_feature_array_batch_uses_configured_order:
    验证按照配置顺序构造批量特征矩阵
  - test_to_feature_array_batch_infers_sorted_names:
    验证未配置特征名称时使用稳定顺序
  - test_feature_array_rejects_invalid_input:
    验证拒绝无效特征输入
  - test_validate_features_reports_missing_and_type_errors:
    验证报告缺失特征和类型错误
  - test_ensure_2d_normalizes_array_shape:
    验证规范化一维和二维数组
  - test_ensure_2d_rejects_unsupported_dimensions:
    验证拒绝不支持的数组维度
"""

from collections.abc import Callable

import numpy as np
import pytest

from datamind.constants import DataType
from datamind.core.inference.features import FeatureTransformer


def test_feature_transformer_normalizes_names() -> None:
    """验证规范化并复制特征名称"""
    names = ["age", "employment_type"]

    result = FeatureTransformer(names).feature_names
    names.append("income")

    assert result == ["age", "employment_type"]
    assert FeatureTransformer().feature_names is None
    assert FeatureTransformer([]).feature_names is None


@pytest.mark.parametrize(
    "feature_names",
    [
        ["age", ""],
        ["age", "   "],
        ["age", "age"],
    ],
)
def test_feature_transformer_rejects_invalid_names(
        feature_names: list[str],
) -> None:
    """验证拒绝空白或重复特征名称"""
    with pytest.raises(ValueError):
        FeatureTransformer(feature_names)


def test_to_feature_array_uses_configured_order() -> None:
    """验证按照配置顺序构造单条特征矩阵"""
    result = FeatureTransformer([
        "age",
        "employment_type",
    ]).transform(
        {
            "employment_type": "salaried",
            "unused": 1,
        }
    )

    assert result.shape == (1, 2)
    assert np.isnan(result[0, 0])
    assert result[0, 1] == "salaried"


def test_to_feature_array_batch_uses_configured_order() -> None:
    """验证按照配置顺序构造批量特征矩阵"""
    result = FeatureTransformer([
        "amount",
        "category",
    ]).transform_batch(
        [
            {"category": "A", "amount": 10},
            {"amount": 20, "category": "B"},
        ]
    )

    assert result.tolist() == [
        [10.0, "A"],
        [20.0, "B"],
    ]


def test_to_feature_array_batch_infers_sorted_names() -> None:
    """验证未配置特征名称时使用稳定顺序"""
    result = FeatureTransformer().transform_batch(
        [
            {"b": 2, "a": 1},
            {"a": 3, "b": 4},
        ]
    )

    assert result.tolist() == [
        [1.0, 2.0],
        [3.0, 4.0],
    ]


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (
            lambda: FeatureTransformer(["age"]).transform({}),
            "features 不能为空",
        ),
        (
            lambda: FeatureTransformer().transform({"age": 30}),
            "feature_names 不能为空",
        ),
        (
            lambda: FeatureTransformer(["age"]).transform_batch([]),
            "features_list 不能为空",
        ),
        (
            lambda: FeatureTransformer(["age"]).transform_batch(
                [{"age": 30}, "invalid"],  # type: ignore[list-item]
            ),
            "批量输入必须全部为特征字典",
        ),
    ],
)
def test_feature_array_rejects_invalid_input(
        operation: Callable[[], object],
        message: str,
) -> None:
    """验证拒绝无效特征输入"""
    with pytest.raises((TypeError, ValueError), match=message):
        operation()


def test_validate_features_reports_missing_and_type_errors() -> None:
    """验证报告缺失特征和类型错误"""
    transformer = FeatureTransformer(
        [
            "age",
            "income",
            "employment_type",
            "is_existing",
        ],
        {
            "age": DataType.NUMERIC,
            "income": DataType.NUMERIC,
            "employment_type": DataType.CATEGORICAL,
            "is_existing": DataType.BOOLEAN,
        },
    )
    missing, type_errors = transformer.validate(
        {
            "age": True,
            "employment_type": 1,
            "is_existing": "yes",
        }
    )

    assert missing == ["income"]
    assert type_errors == [
        ("age", "numeric", "bool"),
        ("employment_type", "categorical", "int"),
        ("is_existing", "boolean", "str"),
    ]


def test_ensure_2d_normalizes_array_shape() -> None:
    """验证规范化一维和二维数组"""
    one_dimensional = FeatureTransformer.ensure_2d(
        np.asarray([1, 2])
    )
    two_dimensional = np.asarray([[1, 2]])

    assert one_dimensional.shape == (1, 2)
    assert (
        FeatureTransformer.ensure_2d(two_dimensional)
        is two_dimensional
    )


def test_ensure_2d_rejects_unsupported_dimensions() -> None:
    """验证拒绝不支持的数组维度"""
    with pytest.raises(ValueError, match="仅支持 1D / 2D"):
        FeatureTransformer.ensure_2d(np.zeros((1, 1, 1)))
