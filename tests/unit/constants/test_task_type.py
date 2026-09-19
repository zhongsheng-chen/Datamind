"""模型任务类型枚举测试

验证 TaskType 的成员、字符串行为、反向构造和支持集合。

核心功能：
  - test_task_type_members_and_values:
    验证枚举包含预期成员和值
  - test_task_type_string_behavior:
    验证枚举成员具有字符串语义
  - test_task_type_can_be_created_from_value:
    验证可通过字符串值反向构造枚举
  - test_supported_task_types_matches_enum_values:
    验证支持集合与枚举值一致且仅包含字符串
  - test_invalid_task_type_raises_value_error:
    验证非法值不能构造枚举
"""

from enum import Enum

import pytest

from datamind.constants.task_type import (
    SUPPORTED_TASK_TYPES,
    TaskType,
)


EXPECTED_TASK_TYPES = {
    TaskType.SCORING: "scoring",
    TaskType.CLASSIFICATION: "classification",
}


def test_task_type_members_and_values() -> None:
    """测试模型任务类型枚举包含预期成员和值"""
    assert {
        member: member.value
        for member in TaskType
    } == EXPECTED_TASK_TYPES


@pytest.mark.parametrize(
    (
        "member",
        "expected_value",
    ),
    EXPECTED_TASK_TYPES.items(),
)
def test_task_type_string_behavior(
        member: TaskType,
        expected_value: str,
) -> None:
    """测试模型任务类型枚举具有字符串语义"""
    assert isinstance(member, str)
    assert isinstance(member, Enum)
    assert str(member) == expected_value
    assert member == expected_value


@pytest.mark.parametrize(
    (
        "value",
        "expected_member",
    ),
    [
        (
            "scoring",
            TaskType.SCORING,
        ),
        (
            "classification",
            TaskType.CLASSIFICATION,
        ),
    ],
)
def test_task_type_can_be_created_from_value(
        value: str,
        expected_member: TaskType,
) -> None:
    """测试可以通过字符串值反向构造模型任务类型"""
    assert TaskType(value) is expected_member


def test_supported_task_types_matches_enum_values() -> None:
    """测试支持集合与枚举值保持一致且仅包含字符串"""
    assert SUPPORTED_TASK_TYPES == frozenset(
        member.value
        for member in TaskType
    )
    assert all(
        type(value) is str
        for value in SUPPORTED_TASK_TYPES
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "SCORING",
        "classify",
        "unknown",
    ],
)
def test_invalid_task_type_raises_value_error(
        value: str,
) -> None:
    """测试非法模型任务类型不能构造枚举"""
    with pytest.raises(ValueError):
        TaskType(value)
