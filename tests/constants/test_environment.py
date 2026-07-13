# tests/constants/test_environment.py

"""服务环境枚举测试

验证 Environment 的成员、字符串行为和支持集合。

核心功能：
  - test_environment_members_and_values:
    验证枚举包含预期成员和值
  - test_environment_string_behavior:
    验证枚举成员具有字符串语义
  - test_environment_can_be_created_from_value:
    验证可通过字符串值反向构造枚举
  - test_supported_environments_contains_all_values:
    验证支持集合包含全部环境值
  - test_supported_environments_matches_enum_members:
    验证支持集合与枚举成员一致
  - test_invalid_environment_raises_value_error:
    验证非法值不能构造枚举
"""

from enum import Enum

import pytest

from datamind.constants.environment import (
    Environment,
    SUPPORTED_ENVIRONMENTS,
)


EXPECTED_ENVIRONMENTS = {
    Environment.DEVELOPMENT: "development",
    Environment.TESTING: "testing",
    Environment.STAGING: "staging",
    Environment.PRODUCTION: "production",
}


def test_environment_members_and_values() -> None:
    """测试服务环境枚举包含预期成员和值"""
    assert {
        member: member.value
        for member in Environment
    } == EXPECTED_ENVIRONMENTS


@pytest.mark.parametrize(
    (
        "member",
        "expected_value",
    ),
    EXPECTED_ENVIRONMENTS.items(),
)
def test_environment_string_behavior(
        member: Environment,
        expected_value: str,
) -> None:
    """测试服务环境枚举具有字符串语义"""
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
            "development",
            Environment.DEVELOPMENT,
        ),
        (
            "testing",
            Environment.TESTING,
        ),
        (
            "staging",
            Environment.STAGING,
        ),
        (
            "production",
            Environment.PRODUCTION,
        ),
    ],
)
def test_environment_can_be_created_from_value(
        value: str,
        expected_member: Environment,
) -> None:
    """测试可以通过字符串值反向构造服务环境"""
    assert Environment(value) is expected_member


def test_supported_environments_contains_all_values() -> None:
    """测试支持集合包含全部服务环境值"""
    assert SUPPORTED_ENVIRONMENTS == frozenset(
        EXPECTED_ENVIRONMENTS.values()
    )


def test_supported_environments_matches_enum_members() -> None:
    """测试支持集合与枚举成员保持一致"""
    assert {
        str(environment)
        for environment in SUPPORTED_ENVIRONMENTS
    } == {
        member.value
        for member in Environment
    }


@pytest.mark.parametrize(
    "value",
    [
        "",
        "dev",
        "PRODUCTION",
        "unknown",
    ],
)
def test_invalid_environment_raises_value_error(
        value: str,
) -> None:
    """测试非法服务环境不能构造枚举"""
    with pytest.raises(ValueError):
        Environment(value)
