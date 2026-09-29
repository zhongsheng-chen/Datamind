"""认证提供方包公共导出测试.

验证认证提供方包公开 API 的完整性和可访问性。

核心功能：
  - test_provider_exports_expected_public_api:
    验证 __all__ 包含完整且准确的认证提供方 API
  - test_all_declared_exports_are_available:
    验证声明的认证提供方对象均可从包级访问
"""

import datamind.auth.providers as providers


EXPECTED_EXPORTS = {
    "BaseAuthProvider",
    "PasswordCredentials",
    "ProviderCredentials",
    "ProviderIdentity",
    "LocalProviderConfig",
    "LocalAuthProvider",
}


def test_provider_exports_expected_public_api() -> None:
    """测试认证提供方包公开完整且准确的 API."""
    assert set(providers.__all__) == EXPECTED_EXPORTS
    assert len(providers.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的认证提供方对象均可访问."""
    for name in providers.__all__:
        assert hasattr(providers, name), name
