"""存储类型枚举测试

验证 StorageType 的成员、字符串行为和支持集合。

核心功能：
  - test_storage_type_members_and_values:
    验证枚举包含预期成员和值
  - test_storage_type_string_behavior:
    验证枚举成员具有字符串语义
  - test_storage_type_can_be_created_from_value:
    验证可通过字符串值反向构造枚举
  - test_supported_storage_types_contains_all_members:
    验证支持集合包含全部枚举成员
  - test_supported_storage_types_matches_enum_values:
    验证支持集合与枚举值一致
  - test_invalid_storage_type_raises_value_error:
    验证非法值不能构造枚举
"""

from enum import Enum

import pytest

from datamind.constants.storage_type import (
    StorageType,
    SUPPORTED_STORAGE_TYPES,
)


EXPECTED_STORAGE_TYPES = {
    StorageType.LOCAL: "local",
    StorageType.MINIO: "minio",
}


def test_storage_type_members_and_values() -> None:
    """测试存储类型枚举包含预期成员和值"""
    assert {
        member: member.value
        for member in StorageType
    } == EXPECTED_STORAGE_TYPES


@pytest.mark.parametrize(
    (
        "member",
        "expected_value",
    ),
    EXPECTED_STORAGE_TYPES.items(),
)
def test_storage_type_string_behavior(
        member: StorageType,
        expected_value: str,
) -> None:
    """测试存储类型枚举具有字符串语义"""
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
            "local",
            StorageType.LOCAL,
        ),
        (
            "minio",
            StorageType.MINIO,
        ),
    ],
)
def test_storage_type_can_be_created_from_value(
        value: str,
        expected_member: StorageType,
) -> None:
    """测试可以通过字符串值反向构造存储类型"""
    assert StorageType(value) is expected_member


def test_supported_storage_types_contains_all_members() -> None:
    """测试支持集合包含全部存储类型"""
    assert SUPPORTED_STORAGE_TYPES == frozenset(
        StorageType
    )


def test_supported_storage_types_matches_enum_values() -> None:
    """测试支持集合与枚举值保持一致"""
    assert {
        str(storage_type)
        for storage_type in SUPPORTED_STORAGE_TYPES
    } == set(
        EXPECTED_STORAGE_TYPES.values()
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "LOCAL",
        "MINIO",
        "s3",
        "unknown",
    ],
)
def test_invalid_storage_type_raises_value_error(
        value: str,
) -> None:
    """测试非法存储类型不能构造枚举"""
    with pytest.raises(ValueError):
        StorageType(value)
