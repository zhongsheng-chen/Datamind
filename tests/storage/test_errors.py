# tests/storage/test_errors.py

"""存储异常测试

验证存储异常的继承关系、消息透传、统一捕获和异常链。

核心功能：
  - test_storage_errors_inherit_from_backend_error:
    验证具体异常继承存储后端异常
  - test_storage_errors_preserve_message:
    验证具体异常保留错误消息
  - test_storage_errors_support_empty_message:
    验证具体异常支持空消息
  - test_storage_errors_can_be_caught_by_base_type:
    验证具体异常可由基础类型统一捕获
  - test_storage_backend_error_preserves_message:
    验证基础异常保留错误消息
  - test_storage_error_preserves_exception_cause:
    验证存储异常保留异常链
"""

import pytest

from datamind.storage.errors import (
    StorageBackendError,
    StorageConnectionError,
    StorageKeyError,
    StorageNotFoundError,
    StoragePermissionError,
)


STORAGE_ERROR_TYPES: tuple[
    type[StorageBackendError],
    ...,
] = (
    StorageKeyError,
    StorageNotFoundError,
    StoragePermissionError,
    StorageConnectionError,
)


@pytest.mark.parametrize(
    "error_type",
    STORAGE_ERROR_TYPES,
    ids=[
        "key",
        "not-found",
        "permission",
        "connection",
    ],
)
def test_storage_errors_inherit_from_backend_error(
    error_type: type[StorageBackendError],
) -> None:
    """测试具体存储异常继承自基础异常"""
    error = error_type(
        "存储操作失败"
    )

    assert isinstance(
        error,
        StorageBackendError,
    )
    assert isinstance(
        error,
        Exception,
    )


@pytest.mark.parametrize(
    "error_type",
    STORAGE_ERROR_TYPES,
    ids=[
        "key",
        "not-found",
        "permission",
        "connection",
    ],
)
def test_storage_errors_preserve_message(
    error_type: type[StorageBackendError],
) -> None:
    """测试具体存储异常保留错误消息"""
    error = error_type(
        "自定义存储错误"
    )

    assert str(error) == "自定义存储错误"
    assert error.args == (
        "自定义存储错误",
    )


@pytest.mark.parametrize(
    "error_type",
    STORAGE_ERROR_TYPES,
    ids=[
        "key",
        "not-found",
        "permission",
        "connection",
    ],
)
def test_storage_errors_support_empty_message(
    error_type: type[StorageBackendError],
) -> None:
    """测试具体存储异常允许不传错误消息"""
    error = error_type()

    assert str(error) == ""
    assert error.args == ()


@pytest.mark.parametrize(
    "error",
    [
        StorageKeyError(
            "非法存储键"
        ),
        StorageNotFoundError(
            "对象不存在"
        ),
        StoragePermissionError(
            "没有访问权限"
        ),
        StorageConnectionError(
            "无法连接存储服务"
        ),
    ],
    ids=[
        "key",
        "not-found",
        "permission",
        "connection",
    ],
)
def test_storage_errors_can_be_caught_by_base_type(
    error: StorageBackendError,
) -> None:
    """测试具体异常可以通过基础类型统一捕获"""
    with pytest.raises(
        StorageBackendError,
    ) as exc_info:
        raise error

    assert exc_info.value is error


def test_storage_backend_error_preserves_message() -> None:
    """测试基础存储异常保留错误消息"""
    error = StorageBackendError(
        "存储后端异常"
    )

    assert str(error) == "存储后端异常"
    assert error.args == (
        "存储后端异常",
    )


def test_storage_error_preserves_exception_cause() -> None:
    """测试存储异常支持保留原始异常链"""
    original_error = RuntimeError(
        "connection reset"
    )

    with pytest.raises(
        StorageConnectionError,
        match="连接对象存储失败",
    ) as exc_info:
        try:
            raise original_error
        except RuntimeError as caught_error:
            raise StorageConnectionError(
                "连接对象存储失败"
            ) from caught_error

    assert exc_info.value.__cause__ is original_error
