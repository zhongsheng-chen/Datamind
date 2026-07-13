# tests/auth/test_exports.py

"""认证包公共导出测试

验证认证包应用层公共 API 的完整性、可访问性和延迟加载行为。

核心功能：
  - test_auth_exports_expected_public_api:
    验证 __all__ 包含完整且准确的应用层 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
  - test_unknown_export_raises_attribute_error:
    验证未知属性遵循标准模块访问语义
"""

import pytest

import datamind.auth as auth


EXPECTED_EXPORTS = {
    "AuthService",
    "create_auth_service",
    "LoginRequest",
    "RefreshTokenRequest",
    "LogoutRequest",
    "TokenResponse",
    "AccessTokenClaims",
    "AuthenticatedUser",
    "UserStatus",
    "AuthError",
    "AuthenticationRequiredError",
    "InvalidCredentialsError",
    "UserDisabledError",
    "UserLockedError",
    "TokenError",
    "InvalidAccessTokenError",
    "AccessTokenExpiredError",
    "InvalidRefreshTokenError",
    "RefreshTokenExpiredError",
    "RefreshTokenRevokedError",
    "PermissionDeniedError",
    "normalize_permission",
    "permission_implies",
    "has_permission",
    "has_any_permission",
    "has_all_permissions",
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
}


def test_auth_exports_expected_public_api() -> None:
    """测试认证包公开完整且准确的应用层 API"""
    assert set(auth.__all__) == EXPECTED_EXPORTS
    assert len(auth.__all__) == len(EXPECTED_EXPORTS)
    assert EXPECTED_EXPORTS <= set(dir(auth))


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in auth.__all__:
        assert hasattr(auth, name), name


def test_unknown_export_raises_attribute_error() -> None:
    """测试未知包级属性抛出 AttributeError"""
    with pytest.raises(AttributeError):
        getattr(
            auth,
            "UnknownAuthExport",
        )
