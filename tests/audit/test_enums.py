# tests/audit/test_enums.py

"""审计枚举测试

验证审计字符串枚举基类、审计来源和审计状态。

核心功能：
  - test_base_enum_inheritance: 验证字符串枚举基类继承关系
  - test_audit_source_values: 验证审计来源枚举值
  - test_audit_status_values: 验证审计状态枚举值
  - test_audit_enum_string: 验证枚举字符串转换
  - test_audit_enum_rejects_invalid_value: 验证拒绝非法枚举值
"""

from enum import Enum

import pytest

from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
    BaseEnum,
)


def test_base_enum_inheritance() -> None:
    """验证字符串枚举基类继承关系"""
    assert issubclass(
        BaseEnum,
        str,
    )
    assert issubclass(
        BaseEnum,
        Enum,
    )
    assert issubclass(
        AuditSource,
        BaseEnum,
    )
    assert issubclass(
        AuditStatus,
        BaseEnum,
    )


def test_audit_source_values() -> None:
    """验证审计来源枚举值"""
    assert [
        source.value
        for source in AuditSource
    ] == [
        "http",
        "cli",
        "system",
        "worker",
        "scheduler",
    ]


def test_audit_status_values() -> None:
    """验证审计状态枚举值"""
    assert [
        status.value
        for status in AuditStatus
    ] == [
        "success",
        "failed",
    ]


@pytest.mark.parametrize(
    (
        "member",
        "expected",
    ),
    [
        (
            AuditSource.HTTP,
            "http",
        ),
        (
            AuditSource.CLI,
            "cli",
        ),
        (
            AuditSource.SYSTEM,
            "system",
        ),
        (
            AuditSource.WORKER,
            "worker",
        ),
        (
            AuditSource.SCHEDULER,
            "scheduler",
        ),
        (
            AuditStatus.SUCCESS,
            "success",
        ),
        (
            AuditStatus.FAILED,
            "failed",
        ),
    ],
)
def test_audit_enum_string(
        member: BaseEnum,
        expected: str,
) -> None:
    """验证枚举字符串转换"""
    assert str(
        member
    ) == expected


@pytest.mark.parametrize(
    (
        "enum_type",
        "value",
        "expected_message",
    ),
    [
        (
            AuditSource,
            "api",
            "'api' is not a valid AuditSource",
        ),
        (
            AuditStatus,
            "pending",
            "'pending' is not a valid AuditStatus",
        ),
    ],
)
def test_audit_enum_rejects_invalid_value(
        enum_type: type[BaseEnum],
        value: str,
        expected_message: str,
) -> None:
    """验证拒绝非法枚举值"""
    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        enum_type(
            value
        )
