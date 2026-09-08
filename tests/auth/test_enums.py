"""认证枚举测试

验证认证状态枚举的成员、字符串语义和序列化行为。

核心功能：
  - test_enum_members:
    验证枚举成员和值
  - test_enum_uses_string_semantics:
    验证枚举具有一致的字符串语义
  - test_enum_can_be_created_from_string:
    验证可通过字符串值创建枚举
  - test_enum_rejects_invalid_value:
    验证枚举拒绝非法字符串
  - test_enum_works_as_dictionary_key:
    验证枚举与字符串具有相同的字典键语义"""

import json

import pytest

from datamind.auth.enums import (
    BaseEnum,
    GrantStatus,
    RoleStatus,
    TokenStatus,
    UserStatus,
)


ENUM_CASES = [
    (
        UserStatus,
        {
            "ACTIVE": "active",
            "DISABLED": "disabled",
            "LOCKED": "locked",
        },
    ),
    (
        RoleStatus,
        {
            "ACTIVE": "active",
            "INACTIVE": "inactive",
        },
    ),
    (
        GrantStatus,
        {
            "ACTIVE": "active",
            "REVOKED": "revoked",
        },
    ),
    (
        TokenStatus,
        {
            "ACTIVE": "active",
            "REVOKED": "revoked",
        },
    ),
]


@pytest.mark.parametrize(
    ("enum_class", "expected_members"),
    ENUM_CASES,
)
def test_enum_members(
        enum_class: type[BaseEnum],
        expected_members: dict[str, str],
) -> None:
    """验证枚举成员和值"""
    assert {
        name: member.value
        for name, member in enum_class.__members__.items()
    } == expected_members


@pytest.mark.parametrize(
    "enum_member",
    [
        UserStatus.ACTIVE,
        RoleStatus.ACTIVE,
        GrantStatus.REVOKED,
        TokenStatus.ACTIVE,
    ],
)
def test_enum_uses_string_semantics(
        enum_member: BaseEnum,
) -> None:
    """验证枚举具有一致的字符串语义"""
    assert isinstance(enum_member, str)
    assert str(enum_member) == enum_member.value
    assert enum_member == enum_member.value
    assert json.dumps(enum_member) == json.dumps(
        enum_member.value
    )


@pytest.mark.parametrize(
    ("enum_class", "value"),
    [
        (UserStatus, "active"),
        (RoleStatus, "inactive"),
        (GrantStatus, "revoked"),
        (TokenStatus, "active"),
    ],
)
def test_enum_can_be_created_from_string(
        enum_class: type[BaseEnum],
        value: str,
) -> None:
    """验证可通过字符串值创建枚举"""
    assert enum_class(value).value == value


@pytest.mark.parametrize(
    "enum_class",
    [
        UserStatus,
        RoleStatus,
        GrantStatus,
        TokenStatus,
    ],
)
def test_enum_rejects_invalid_value(
        enum_class: type[BaseEnum],
) -> None:
    """验证枚举拒绝非法字符串"""
    with pytest.raises(ValueError):
        enum_class("unknown")


def test_enum_works_as_dictionary_key() -> None:
    """验证枚举与字符串具有相同的字典键语义"""
    values: dict[str, str] = {
        UserStatus.ACTIVE: "matched",
    }

    assert values["active"] == "matched"
