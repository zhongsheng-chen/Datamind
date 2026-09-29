"""审计异常测试.

验证审计异常的继承关系、默认消息和自定义消息。

核心功能：
  - test_audit_errors_use_default_message:
    验证默认异常消息
  - test_audit_errors_accept_custom_message:
    验证自定义异常消息
  - test_audit_errors_inherit_from_audit_error:
    验证异常继承关系
  - test_audit_errors_can_be_caught_by_base_type:
    验证基础异常捕获
  - test_audit_error_preserves_exception_cause:
    验证异常链保留
"""

import pytest

from datamind.audit.errors import (
    AuditError,
    AuditValidationError,
    AuditWriteError,
)


@pytest.mark.parametrize(
    (
        "error_type",
        "default_message",
    ),
    [
        (
            AuditValidationError,
            "审计事件校验失败",
        ),
        (
            AuditWriteError,
            "审计事件写入失败",
        ),
    ],
    ids=[
        "validation",
        "write",
    ],
)
def test_audit_errors_use_default_message(
    error_type: type[AuditError],
    default_message: str,
) -> None:
    """测试各审计异常的默认错误消息."""
    error = error_type()

    assert str(error) == default_message
    assert error.args == (
        default_message,
    )


@pytest.mark.parametrize(
    "error_type",
    [
        AuditValidationError,
        AuditWriteError,
    ],
    ids=[
        "validation",
        "write",
    ],
)
def test_audit_errors_accept_custom_message(
    error_type: type[AuditError],
) -> None:
    """测试各审计异常接受自定义错误消息."""
    error = error_type(
        "自定义审计错误"
    )

    assert str(error) == "自定义审计错误"
    assert error.args == (
        "自定义审计错误",
    )


@pytest.mark.parametrize(
    "error_type",
    [
        AuditValidationError,
        AuditWriteError,
    ],
    ids=[
        "validation",
        "write",
    ],
)
def test_audit_errors_inherit_from_audit_error(
    error_type: type[AuditError],
) -> None:
    """测试具体审计异常继承自 AuditError."""
    error = error_type()

    assert isinstance(
        error,
        AuditError,
    )
    assert isinstance(
        error,
        Exception,
    )


@pytest.mark.parametrize(
    "error",
    [
        AuditValidationError(),
        AuditWriteError(),
    ],
    ids=[
        "validation",
        "write",
    ],
)
def test_audit_errors_can_be_caught_by_base_type(
    error: AuditError,
) -> None:
    """测试具体异常可以通过 AuditError 统一捕获."""
    with pytest.raises(
        AuditError,
    ) as exc_info:
        raise error

    assert exc_info.value is error


def test_audit_error_accepts_message() -> None:
    """测试基础审计异常保留错误消息."""
    error = AuditError(
        "审计模块异常"
    )

    assert str(error) == "审计模块异常"
    assert error.args == (
        "审计模块异常",
    )


def test_audit_error_preserves_exception_cause() -> None:
    """测试审计异常支持保留原始异常链."""
    original_error = RuntimeError(
        "database unavailable"
    )

    try:
        raise original_error
    except RuntimeError as exc:
        try:
            raise AuditWriteError(
                "审计事件写入失败"
            ) from exc
        except AuditWriteError as audit_error:
            captured_error = audit_error

    assert captured_error.__cause__ is original_error
