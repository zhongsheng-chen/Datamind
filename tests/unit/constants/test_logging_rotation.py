"""日志轮转枚举测试.

验证日志轮转策略、轮转时间、字符串转换和支持集合。

核心功能：
  - test_rotation_type_value:
    验证日志轮转策略枚举值
  - test_rotation_when_value:
    验证日志轮转时间枚举值
  - test_rotation_type_string_conversion:
    验证轮转策略字符串转换
  - test_rotation_when_string_conversion:
    验证轮转时间字符串转换
  - test_supported_rotation_types:
    验证轮转策略支持集合及元素类型
  - test_supported_rotation_when:
    验证轮转时间支持集合及元素类型
"""

import pytest

from datamind.constants.logging_rotation import (
    RotationType,
    RotationWhen,
    SUPPORTED_ROTATION_TYPES,
    SUPPORTED_ROTATION_WHEN,
)


@pytest.mark.parametrize(
    ("rotation_type", "expected"),
    [
        (RotationType.TIME, "time"),
        (RotationType.SIZE, "size"),
    ],
)
def test_rotation_type_value(
    rotation_type: RotationType,
    expected: str,
) -> None:
    """测试日志轮转策略枚举值."""
    assert rotation_type.value == expected


@pytest.mark.parametrize(
    ("rotation_when", "expected"),
    [
        (RotationWhen.MIDNIGHT, "MIDNIGHT"),
        (RotationWhen.HOUR, "H"),
        (RotationWhen.MINUTE, "M"),
        (RotationWhen.SECOND, "S"),
        (RotationWhen.MONDAY, "W0"),
        (RotationWhen.TUESDAY, "W1"),
        (RotationWhen.WEDNESDAY, "W2"),
        (RotationWhen.THURSDAY, "W3"),
        (RotationWhen.FRIDAY, "W4"),
        (RotationWhen.SATURDAY, "W5"),
        (RotationWhen.SUNDAY, "W6"),
    ],
)
def test_rotation_when_value(
    rotation_when: RotationWhen,
    expected: str,
) -> None:
    """测试日志轮转时间枚举值."""
    assert rotation_when.value == expected


@pytest.mark.parametrize(
    "rotation_type",
    list(RotationType),
)
def test_rotation_type_string_conversion(
    rotation_type: RotationType,
) -> None:
    """测试日志轮转策略字符串转换."""
    assert str(rotation_type) == rotation_type.value


@pytest.mark.parametrize(
    "rotation_when",
    list(RotationWhen),
)
def test_rotation_when_string_conversion(
    rotation_when: RotationWhen,
) -> None:
    """测试日志轮转时间字符串转换."""
    assert str(rotation_when) == rotation_when.value


def test_supported_rotation_types() -> None:
    """测试支持的日志轮转策略集合."""
    assert SUPPORTED_ROTATION_TYPES == frozenset(
        member.value
        for member in RotationType
    )
    assert all(
        type(value) is str
        for value in SUPPORTED_ROTATION_TYPES
    )


def test_supported_rotation_when() -> None:
    """测试支持的日志轮转时间集合."""
    assert SUPPORTED_ROTATION_WHEN == frozenset(
        member.value
        for member in RotationWhen
    )
    assert all(
        type(value) is str
        for value in SUPPORTED_ROTATION_WHEN
    )
