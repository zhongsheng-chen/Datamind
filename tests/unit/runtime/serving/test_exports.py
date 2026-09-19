"""运行时推理服务包公共导出测试

验证运行时推理服务包公开 API 的完整性和可访问性。

核心功能：
  - test_serving_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import pytest

import datamind.runtime.serving as serving


EXPECTED_EXPORTS = {
    "BaseRuntimeService",
    "ClassificationService",
    "RuntimeServiceFactory",
    "ScoringService",
}


def test_serving_exports_expected_public_api() -> None:
    """测试推理服务包公开完整且准确的 API"""
    assert set(serving.__all__) == EXPECTED_EXPORTS
    assert len(serving.__all__) == len(EXPECTED_EXPORTS)


@pytest.mark.framework
def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in serving.__all__:
        assert hasattr(serving, name), name
