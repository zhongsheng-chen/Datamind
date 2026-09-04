# tests/core/test_exports.py

"""核心包公共导出测试

验证核心包公开 API 的完整性和可访问性。

核心功能：
  - test_core_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.core as core


EXPECTED_EXPORTS = {
    "Inference",
    "ModelCapability",
}


def test_core_exports_expected_public_api() -> None:
    """测试核心包公开完整且准确的 API"""
    assert set(core.__all__) == EXPECTED_EXPORTS
    assert len(core.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in core.__all__:
        assert hasattr(core, name), name
