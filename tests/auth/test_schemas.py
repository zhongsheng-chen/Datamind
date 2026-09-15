"""认证数据结构测试

验证登录、令牌和已认证用户数据结构的校验与默认行为。

核心功能：
  - test_login_request_normalizes_username:
    验证登录请求规范化用户名
  - test_login_request_protects_password:
    验证登录请求不会暴露密码
  - test_login_request_validates_fields:
    验证登录请求拒绝空字段
  - test_refresh_token_requests_protect_token:
    验证刷新令牌请求保护原始令牌
  - test_token_response_uses_defaults:
    验证令牌响应默认使用 bearer 类型
  - test_token_response_allows_missing_refresh_token:
    验证应急账户响应可以不含刷新令牌
  - test_token_response_validates_fields:
    验证令牌响应拒绝非法字段
  - test_access_token_claims_uses_defaults:
    验证访问令牌声明使用独立的列表默认值
  - test_access_token_claims_validates_fields:
    验证访问令牌声明拒绝非法字段
  - test_authenticated_user_maps_status:
    验证已认证用户映射状态枚举
  - test_authenticated_user_uses_defaults:
    验证已认证用户使用空权限默认值
  - test_removed_provider_fields_are_rejected:
    验证已移除的认证来源字段不再被接受"""

import pytest
from pydantic import ValidationError

from datamind.auth.enums import UserStatus
from datamind.auth.schemas import (
    AccessTokenClaims,
    AuthenticatedUser,
    LoginRequest,
    LogoutRequest,
    LogoutResult,
    RefreshTokenRequest,
    TokenResponse,
)


def test_login_request_normalizes_username() -> None:
    """验证登录请求规范化用户名"""
    request = LoginRequest.model_validate({
        "username": "  admin  ",
        "password": "P@ssw1rd",
    })

    assert request.username == "admin"
    assert request.password.get_secret_value() == "P@ssw1rd"


def test_login_request_protects_password() -> None:
    """验证登录请求不会暴露密码"""
    request = LoginRequest.model_validate({
        "username": "admin",
        "password": "P@ssw1rd",
    })

    assert "P@ssw1rd" not in repr(request)
    assert request.model_dump()["password"] != "P@ssw1rd"


@pytest.mark.parametrize(
    "values",
    [
        {
            "username": "",
            "password": "password",
        },
        {
            "username": "admin",
            "password": "",
        },
    ],
)
def test_login_request_validates_fields(
        values: dict[str, str],
) -> None:
    """验证登录请求拒绝空字段"""
    with pytest.raises(ValidationError):
        LoginRequest.model_validate(
            values
        )


@pytest.mark.parametrize(
    "schema_class",
    [
        RefreshTokenRequest,
        LogoutRequest,
    ],
)
def test_refresh_token_requests_protect_token(
        schema_class: type[
            RefreshTokenRequest
            | LogoutRequest
        ],
) -> None:
    """验证刷新令牌请求保护原始令牌"""
    request = schema_class.model_validate({
        "refresh_token": "refresh-token",
    })

    assert request.refresh_token.get_secret_value() == (
        "refresh-token"
    )
    assert "refresh-token" not in repr(request)


def test_logout_result_preserves_user_identity() -> None:
    """验证退出结果携带撤销状态和用户身份"""
    result = LogoutResult(
        revoked=True,
        user_id="usr_test",
        username="admin",
    )

    assert result.revoked is True
    assert result.user_id == "usr_test"
    assert result.username == "admin"


def test_token_response_uses_defaults() -> None:
    """验证令牌响应默认使用 bearer 类型"""
    response = TokenResponse(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=1800,
    )

    assert response.token_type == "bearer"
    assert response.expires_in == 1800


def test_token_response_allows_missing_refresh_token() -> None:
    """验证应急账户响应可以不含刷新令牌"""
    response = TokenResponse(
        access_token="access-token",
        expires_in=900,
    )

    assert response.refresh_token is None


@pytest.mark.parametrize(
    "values",
    [
        {
            "access_token": "",
            "expires_in": 1800,
        },
        {
            "access_token": "access-token",
            "expires_in": 0,
        },
    ],
)
def test_token_response_validates_fields(
        values: dict[str, object],
) -> None:
    """验证令牌响应拒绝非法字段"""
    with pytest.raises(ValidationError):
        TokenResponse.model_validate(
            values
        )


def test_access_token_claims_uses_defaults() -> None:
    """验证访问令牌声明使用独立的列表默认值"""
    first = AccessTokenClaims(
        sub="usr_test",
        type="access",
        iat=100,
        exp=200,
    )
    second = AccessTokenClaims(
        sub="usr_other",
        type="access",
        iat=100,
        exp=200,
    )
    first.roles.append("admin")

    assert first.roles == ["admin"]
    assert second.roles == []
    assert second.permissions == []


@pytest.mark.parametrize(
    "values",
    [
        {
            "sub": "",
            "type": "access",
            "iat": 100,
            "exp": 200,
        },
        {
            "sub": "usr_test",
            "type": "refresh",
            "iat": 100,
            "exp": 200,
        },
        {
            "sub": "usr_test",
            "type": "access",
            "iat": -1,
            "exp": 200,
        },
    ],
)
def test_access_token_claims_validates_fields(
        values: dict[str, object],
) -> None:
    """验证访问令牌声明拒绝非法字段"""
    with pytest.raises(ValidationError):
        AccessTokenClaims.model_validate(
            values
        )


def test_authenticated_user_maps_status() -> None:
    """验证已认证用户映射状态枚举"""
    user = AuthenticatedUser.model_validate({
        "user_id": "usr_test",
        "username": "admin",
        "display_name": "系统管理员",
        "email": "admin@example.com",
        "status": "active",
        "roles": ["admin"],
        "permissions": ["model.*"],
    })

    assert user.status == UserStatus.ACTIVE
    assert user.roles == ["admin"]
    assert user.permissions == ["model.*"]


def test_authenticated_user_uses_defaults() -> None:
    """验证已认证用户使用空权限默认值"""
    user = AuthenticatedUser(
        user_id="usr_test",
        username="admin",
        status=UserStatus.ACTIVE,
    )

    assert user.display_name is None
    assert user.email is None
    assert user.roles == []
    assert user.permissions == []


@pytest.mark.parametrize(
    "schema_class, values",
    [
        (
            LoginRequest,
            {
                "username": "admin",
                "password": "password",
                "provider": "local",
            },
        ),
        (
            AuthenticatedUser,
            {
                "user_id": "usr_test",
                "username": "admin",
                "status": "active",
                "auth_provider": "local",
            },
        ),
    ],
)
def test_removed_provider_fields_are_rejected(
        schema_class: type[
            LoginRequest
            | AuthenticatedUser
        ],
        values: dict[str, object],
) -> None:
    """验证已移除的认证来源字段不再被接受"""
    with pytest.raises(ValidationError):
        schema_class.model_validate(
            values
        )
