# tests/auth/test_errors.py

"""认证异常测试

验证认证异常的默认消息、自定义消息、异常参数和继承关系。

核心功能：
  - test_auth_errors_use_default_messages:
    验证认证异常使用各自默认消息
  - test_auth_errors_accept_custom_message:
    验证认证异常支持自定义消息
  - test_auth_errors_preserve_empty_message:
    验证显式传入空字符串时不会替换为默认消息
  - test_auth_errors_store_message:
    验证异常消息同时保存到 message 和 args
  - test_auth_errors_inherit_from_auth_error:
    验证所有认证业务异常继承 AuthError
  - test_token_errors_inherit_from_token_error:
    验证令牌异常继承 TokenError
  - test_non_token_errors_do_not_inherit_from_token_error:
    验证非令牌异常不继承 TokenError
  - test_auth_error_can_be_caught_as_exception:
    验证认证异常可作为标准 Exception 捕获
  - test_token_errors_can_be_caught_uniformly:
    验证令牌异常可通过 TokenError 统一捕获
  - test_exception_class_default_messages:
    验证异常类默认消息定义
"""

import pytest

from datamind.auth.errors import (
    AccessTokenExpiredError,
    AuthenticationRequiredError,
    AuthError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    PermissionDeniedError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    TokenError,
    UserDisabledError,
    UserLockedError,
)


ERROR_CASES = [
    (
        AuthError,
        "认证失败",
    ),
    (
        AuthenticationRequiredError,
        "用户尚未认证",
    ),
    (
        InvalidCredentialsError,
        "用户名或密码错误",
    ),
    (
        UserDisabledError,
        "用户已停用",
    ),
    (
        UserLockedError,
        "用户已锁定",
    ),
    (
        TokenError,
        "令牌无效",
    ),
    (
        InvalidAccessTokenError,
        "访问令牌无效",
    ),
    (
        AccessTokenExpiredError,
        "访问令牌已过期",
    ),
    (
        InvalidRefreshTokenError,
        "刷新令牌无效",
    ),
    (
        RefreshTokenExpiredError,
        "刷新令牌已过期",
    ),
    (
        RefreshTokenRevokedError,
        "刷新令牌已撤销",
    ),
    (
        PermissionDeniedError,
        "用户权限不足",
    ),
]


TOKEN_ERROR_CLASSES = [
    TokenError,
    InvalidAccessTokenError,
    AccessTokenExpiredError,
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
]


NON_TOKEN_ERROR_CLASSES = [
    AuthenticationRequiredError,
    InvalidCredentialsError,
    UserDisabledError,
    UserLockedError,
    PermissionDeniedError,
]


@pytest.mark.parametrize(
    (
        "error_class",
        "expected_message",
    ),
    ERROR_CASES,
)
def test_auth_errors_use_default_messages(
        error_class: type[AuthError],
        expected_message: str,
) -> None:
    """验证认证异常使用各自默认消息"""
    error = error_class()

    assert str(
        error
    ) == expected_message
    assert error.message == expected_message


@pytest.mark.parametrize(
    "error_class",
    [
        error_class
        for error_class, _
        in ERROR_CASES
    ],
)
def test_auth_errors_accept_custom_message(
        error_class: type[AuthError],
) -> None:
    """验证认证异常支持自定义消息"""
    custom_message = "自定义认证异常消息"
    error = error_class(
        custom_message
    )

    assert str(
        error
    ) == custom_message
    assert error.message == custom_message


@pytest.mark.parametrize(
    "error_class",
    [
        error_class
        for error_class, _
        in ERROR_CASES
    ],
)
def test_auth_errors_preserve_empty_message(
        error_class: type[AuthError],
) -> None:
    """验证显式传入空字符串时不会替换为默认消息"""
    error = error_class(
        ""
    )

    assert str(
        error
    ) == ""
    assert error.message == ""


@pytest.mark.parametrize(
    (
        "error_class",
        "expected_message",
    ),
    ERROR_CASES,
)
def test_auth_errors_store_message(
        error_class: type[AuthError],
        expected_message: str,
) -> None:
    """验证异常消息同时保存到 message 和 args"""
    error = error_class()

    assert error.message == expected_message
    assert error.args == (
        expected_message,
    )


@pytest.mark.parametrize(
    "error_class",
    [
        error_class
        for error_class, _
        in ERROR_CASES
    ],
)
def test_auth_errors_inherit_from_auth_error(
        error_class: type[AuthError],
) -> None:
    """验证所有认证业务异常继承 AuthError"""
    error = error_class()

    assert isinstance(
        error,
        AuthError,
    )
    assert isinstance(
        error,
        Exception,
    )


@pytest.mark.parametrize(
    "error_class",
    TOKEN_ERROR_CLASSES,
)
def test_token_errors_inherit_from_token_error(
        error_class: type[TokenError],
) -> None:
    """验证令牌异常继承 TokenError"""
    error = error_class()

    assert isinstance(
        error,
        TokenError,
    )
    assert isinstance(
        error,
        AuthError,
    )


@pytest.mark.parametrize(
    "error_class",
    NON_TOKEN_ERROR_CLASSES,
)
def test_non_token_errors_do_not_inherit_from_token_error(
        error_class: type[AuthError],
) -> None:
    """验证非令牌异常不继承 TokenError"""
    error = error_class()

    assert not isinstance(
        error,
        TokenError,
    )


@pytest.mark.parametrize(
    "error_class",
    [
        error_class
        for error_class, _
        in ERROR_CASES
    ],
)
def test_auth_error_can_be_caught_as_exception(
        error_class: type[AuthError],
) -> None:
    """验证认证异常可作为标准 Exception 捕获"""
    with pytest.raises(
            Exception
    ) as exc_info:
        raise error_class()

    assert isinstance(
        exc_info.value,
        AuthError,
    )


@pytest.mark.parametrize(
    "error_class",
    TOKEN_ERROR_CLASSES,
)
def test_token_errors_can_be_caught_uniformly(
        error_class: type[TokenError],
) -> None:
    """验证令牌异常可通过 TokenError 统一捕获"""
    with pytest.raises(
            TokenError
    ) as exc_info:
        raise error_class()

    assert type(
        exc_info.value
    ) is error_class


@pytest.mark.parametrize(
    (
        "error_class",
        "expected_message",
    ),
    ERROR_CASES,
)
def test_exception_class_default_messages(
        error_class: type[AuthError],
        expected_message: str,
) -> None:
    """验证异常类默认消息定义"""
    assert (
        error_class.default_message
        == expected_message
    )


def test_access_token_errors_share_token_base() -> None:
    """验证访问令牌异常共享令牌基础异常"""
    assert issubclass(
        InvalidAccessTokenError,
        TokenError,
    )
    assert issubclass(
        AccessTokenExpiredError,
        TokenError,
    )


def test_refresh_token_errors_share_token_base() -> None:
    """验证刷新令牌异常共享令牌基础异常"""
    assert issubclass(
        InvalidRefreshTokenError,
        TokenError,
    )
    assert issubclass(
        RefreshTokenExpiredError,
        TokenError,
    )
    assert issubclass(
        RefreshTokenRevokedError,
        TokenError,
    )


def test_auth_error_preserves_exception_chaining() -> None:
    """验证认证异常支持标准异常链"""
    source_error = ValueError(
        "原始错误"
    )

    try:
        raise source_error
    except ValueError as exc:
        with pytest.raises(
                AuthError
        ) as exc_info:
            raise AuthError(
                "认证处理失败"
            ) from exc

    assert (
        exc_info.value.__cause__
        is source_error
    )
