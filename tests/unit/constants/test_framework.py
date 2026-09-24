"""模型框架枚举测试.

验证 Framework 的成员、字符串行为和支持集合。

核心功能：
  - test_framework_members_and_values:
    验证枚举包含预期成员和值
  - test_framework_string_behavior:
    验证枚举成员具有字符串语义
  - test_framework_can_be_created_from_value:
    验证可通过字符串值反向构造枚举
  - test_supported_frameworks_contains_all_members:
    验证支持集合包含全部枚举成员
  - test_supported_frameworks_matches_enum_values:
    验证支持集合与枚举值一致
  - test_invalid_framework_raises_value_error:
    验证非法值不能构造枚举
"""

from enum import Enum

import pytest

from datamind.constants.framework import (
    Framework,
    SUPPORTED_FRAMEWORKS,
)


EXPECTED_FRAMEWORKS = {
    Framework.SKLEARN: "sklearn",
    Framework.XGBOOST: "xgboost",
    Framework.LIGHTGBM: "lightgbm",
    Framework.CATBOOST: "catboost",
}


def test_framework_members_and_values() -> None:
    """测试模型框架枚举包含预期成员和值."""
    assert {
        member: member.value
        for member in Framework
    } == EXPECTED_FRAMEWORKS


@pytest.mark.parametrize(
    (
        "member",
        "expected_value",
    ),
    EXPECTED_FRAMEWORKS.items(),
)
def test_framework_string_behavior(
        member: Framework,
        expected_value: str,
) -> None:
    """测试模型框架枚举具有字符串语义."""
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
            "sklearn",
            Framework.SKLEARN,
        ),
        (
            "xgboost",
            Framework.XGBOOST,
        ),
        (
            "lightgbm",
            Framework.LIGHTGBM,
        ),
        (
            "catboost",
            Framework.CATBOOST,
        ),
    ],
)
def test_framework_can_be_created_from_value(
        value: str,
        expected_member: Framework,
) -> None:
    """测试可以通过字符串值反向构造模型框架."""
    assert Framework(value) is expected_member


def test_supported_frameworks_contains_all_members() -> None:
    """测试支持集合包含全部模型框架."""
    assert SUPPORTED_FRAMEWORKS == frozenset(
        Framework
    )


def test_supported_frameworks_matches_enum_values() -> None:
    """测试支持集合与枚举值保持一致."""
    assert {
        str(framework)
        for framework in SUPPORTED_FRAMEWORKS
    } == set(
        EXPECTED_FRAMEWORKS.values()
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "SKLEARN",
        "scikit-learn",
        "unknown",
    ],
)
def test_invalid_framework_raises_value_error(
        value: str,
) -> None:
    """测试非法模型框架不能构造枚举."""
    with pytest.raises(ValueError):
        Framework(value)
