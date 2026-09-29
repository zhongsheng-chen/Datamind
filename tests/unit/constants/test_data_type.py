"""数据类型枚举测试.

验证 DataType 的成员、字符串行为和支持集合。

核心功能：
  - test_data_type_members_and_values:
    验证枚举包含预期成员和值
  - test_data_type_string_behavior:
    验证枚举成员具有字符串语义
  - test_data_type_can_be_created_from_value:
    验证可通过字符串值反向构造枚举
  - test_supported_data_types_contains_all_members:
    验证支持集合包含全部枚举成员
  - test_supported_data_types_contains_string_values:
    验证支持集合可使用字符串值判断
  - test_invalid_data_type_raises_value_error:
    验证非法值不能构造枚举
"""

from enum import Enum

import pytest

from datamind.constants.data_type import (
    DataType,
    SUPPORTED_DATA_TYPES,
)


EXPECTED_DATA_TYPES = {
    DataType.NUMERIC: "numeric",
    DataType.CATEGORICAL: "categorical",
    DataType.BOOLEAN: "boolean",
    DataType.ANY: "any",
}


def test_data_type_members_and_values() -> None:
    """测试数据类型枚举包含预期成员和值."""
    assert {
        member: member.value
        for member in DataType
    } == EXPECTED_DATA_TYPES


@pytest.mark.parametrize(
    (
        "member",
        "expected_value",
    ),
    EXPECTED_DATA_TYPES.items(),
)
def test_data_type_string_behavior(
        member: DataType,
        expected_value: str,
) -> None:
    """测试枚举成员具有字符串语义."""
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
            "numeric",
            DataType.NUMERIC,
        ),
        (
            "categorical",
            DataType.CATEGORICAL,
        ),
        (
            "boolean",
            DataType.BOOLEAN,
        ),
        (
            "any",
            DataType.ANY,
        ),
    ],
)
def test_data_type_can_be_created_from_value(
        value: str,
        expected_member: DataType,
) -> None:
    """测试可以通过字符串值反向构造枚举."""
    assert DataType(value) is expected_member


def test_supported_data_types_contains_all_members() -> None:
    """测试支持集合包含全部数据类型."""
    assert SUPPORTED_DATA_TYPES == frozenset(
        DataType
    )


def test_supported_data_types_contains_string_values() -> None:
    """测试支持集合可以使用字符串值判断."""
    assert {
        str(member)
        for member in SUPPORTED_DATA_TYPES
    } == set(
        EXPECTED_DATA_TYPES.values()
    )


def test_invalid_data_type_raises_value_error() -> None:
    """测试非法数据类型不能构造枚举."""
    with pytest.raises(ValueError):
        DataType("unknown")
