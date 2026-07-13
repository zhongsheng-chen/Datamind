# tests/constants/test_logging_level.py

"""日志级别枚举测试

验证日志级别枚举值、字符串转换和支持集合。

核心功能：
  - test_log_level_value:
    验证日志级别枚举值
  - test_log_level_string_conversion:
    验证字符串转换返回枚举值
  - test_supported_log_levels:
    验证支持集合包含全部日志级别
"""

import pytest

from datamind.constants.logging_level import (
    LogLevel,
    SUPPORTED_LOG_LEVELS,
)


@pytest.mark.parametrize(
    ("log_level", "expected"),
    [
        (LogLevel.DEBUG, "DEBUG"),
        (LogLevel.INFO, "INFO"),
        (LogLevel.WARNING, "WARNING"),
        (LogLevel.ERROR, "ERROR"),
        (LogLevel.CRITICAL, "CRITICAL"),
    ],
)
def test_log_level_value(
    log_level: LogLevel,
    expected: str,
) -> None:
    """测试日志级别枚举值"""
    assert log_level.value == expected


@pytest.mark.parametrize(
    "log_level",
    list(LogLevel),
)
def test_log_level_string_conversion(log_level: LogLevel) -> None:
    """测试日志级别字符串转换"""
    assert str(log_level) == log_level.value


def test_supported_log_levels() -> None:
    """测试支持的日志级别集合"""
    assert SUPPORTED_LOG_LEVELS == frozenset(LogLevel)
