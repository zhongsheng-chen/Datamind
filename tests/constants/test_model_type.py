# tests/constants/test_model_type.py

"""模型类型枚举测试

验证 ModelType 的成员、字符串行为和支持集合。

核心功能：
  - test_model_type_members_and_values:
    验证枚举包含预期成员和值
  - test_model_type_string_behavior:
    验证枚举成员具有字符串语义
  - test_model_type_can_be_created_from_value:
    验证可通过字符串值反向构造枚举
  - test_supported_model_types_contains_all_members:
    验证支持集合包含全部枚举成员
  - test_supported_model_types_matches_enum_values:
    验证支持集合与枚举值一致
  - test_invalid_model_type_raises_value_error:
    验证非法值不能构造枚举
"""

from enum import Enum

import pytest

from datamind.constants.model_type import (
    ModelType,
    SUPPORTED_MODEL_TYPES,
)


EXPECTED_MODEL_TYPES = {
    ModelType.LOGISTIC_REGRESSION: "logistic_regression",
    ModelType.DECISION_TREE: "decision_tree",
    ModelType.RANDOM_FOREST: "random_forest",
    ModelType.XGBOOST: "xgboost",
    ModelType.LIGHTGBM: "lightgbm",
    ModelType.CATBOOST: "catboost",
}


def test_model_type_members_and_values() -> None:
    """测试模型类型枚举包含预期成员和值"""
    assert {
        member: member.value
        for member in ModelType
    } == EXPECTED_MODEL_TYPES


@pytest.mark.parametrize(
    (
        "member",
        "expected_value",
    ),
    EXPECTED_MODEL_TYPES.items(),
)
def test_model_type_string_behavior(
        member: ModelType,
        expected_value: str,
) -> None:
    """测试模型类型枚举具有字符串语义"""
    assert isinstance(
        member,
        str,
    )
    assert isinstance(
        member,
        Enum,
    )
    assert str(member) == expected_value
    assert member == expected_value


@pytest.mark.parametrize(
    (
        "value",
        "expected_member",
    ),
    [
        (
            "logistic_regression",
            ModelType.LOGISTIC_REGRESSION,
        ),
        (
            "decision_tree",
            ModelType.DECISION_TREE,
        ),
        (
            "random_forest",
            ModelType.RANDOM_FOREST,
        ),
        (
            "xgboost",
            ModelType.XGBOOST,
        ),
        (
            "lightgbm",
            ModelType.LIGHTGBM,
        ),
        (
            "catboost",
            ModelType.CATBOOST,
        ),
    ],
)
def test_model_type_can_be_created_from_value(
        value: str,
        expected_member: ModelType,
) -> None:
    """测试可以通过字符串值反向构造模型类型"""
    assert ModelType(value) is expected_member


def test_supported_model_types_contains_all_members() -> None:
    """测试支持集合包含全部模型类型"""
    assert SUPPORTED_MODEL_TYPES == frozenset(
        ModelType
    )


def test_supported_model_types_matches_enum_values() -> None:
    """测试支持集合与枚举值保持一致"""
    assert {
        str(model_type)
        for model_type in SUPPORTED_MODEL_TYPES
    } == set(
        EXPECTED_MODEL_TYPES.values()
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "LOGISTIC_REGRESSION",
        "logistic-regression",
        "sklearn",
        "unknown",
    ],
)
def test_invalid_model_type_raises_value_error(
        value: str,
) -> None:
    """测试非法模型类型不能构造枚举"""
    with pytest.raises(ValueError):
        ModelType(value)
