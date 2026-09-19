"""存储包公共导出测试

验证存储包公开 API 的完整性和可访问性。

核心功能：
  - test_storage_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.storage as storage


EXPECTED_EXPORTS = {
    "Storage",
    "get_storage",
}


def test_storage_exports_expected_public_api() -> None:
    """测试存储包公开完整且准确的 API"""
    assert set(storage.__all__) == EXPECTED_EXPORTS
    assert len(storage.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in storage.__all__:
        assert hasattr(storage, name), name
