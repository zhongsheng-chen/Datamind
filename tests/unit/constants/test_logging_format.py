"""日志格式枚举测试.

验证 LogFormat 的成员、字符串行为和支持集合。

核心功能：
  - test_log_format_members_and_values:
    验证枚举包含预期成员和值
  - test_log_format_string_behavior:
    验证枚举成员具有字符串语义
  - test_log_format_can_be_created_from_value:
    验证可通过字符串值反向构造枚举
  - test_supported_log_formats_contains_all_members:
    验证支持集合包含全部枚举成员
  - test_supported_log_formats_matches_enum_values:
    验证支持集合与枚举值一致
  - test_invalid_log_format_raises_value_error:
    验证非法值不能构造枚举
"""

from enum import Enum

import pytest

from datamind.constants.logging_format import (
    LogFormat,
    SUPPORTED_LOG_FORMATS,
)


EXPECTED_LOG_FORMATS = {
    LogFormat.TEXT: "text",
    LogFormat.JSON: "json",
}


def test_log_format_members_and_values() -> None:
    """测试日志格式枚举包含预期成员和值."""
    assert {
        member: member.value
        for member in LogFormat
    } == EXPECTED_LOG_FORMATS


@pytest.mark.parametrize(
    (
        "member",
        "expected_value",
    ),
    EXPECTED_LOG_FORMATS.items(),
)
def test_log_format_string_behavior(
        member: LogFormat,
        expected_value: str,
) -> None:
    """测试日志格式枚举具有字符串语义."""
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
            "text",
            LogFormat.TEXT,
        ),
        (
            "json",
            LogFormat.JSON,
        ),
    ],
)
def test_log_format_can_be_created_from_value(
        value: str,
        expected_member: LogFormat,
) -> None:
    """测试可以通过字符串值反向构造日志格式."""
    assert LogFormat(value) is expected_member


def test_supported_log_formats_contains_all_members() -> None:
    """测试支持集合包含全部日志格式."""
    assert SUPPORTED_LOG_FORMATS == frozenset(
        LogFormat
    )


def test_supported_log_formats_matches_enum_values() -> None:
    """测试支持集合与枚举值保持一致."""
    assert {
        str(log_format)
        for log_format in SUPPORTED_LOG_FORMATS
    } == set(
        EXPECTED_LOG_FORMATS.values()
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "TEXT",
        "JSON",
        "xml",
    ],
)
def test_invalid_log_format_raises_value_error(
        value: str,
) -> None:
    """测试非法日志格式不能构造枚举."""
    with pytest.raises(ValueError):
        LogFormat(value)
