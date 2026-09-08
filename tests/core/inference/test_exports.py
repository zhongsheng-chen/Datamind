"""推理包公共导出测试

验证推理包公开 API 的完整性和可访问性。

核心功能：
  - test_inference_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.core.inference as inference


EXPECTED_EXPORTS = {
    "Inference",
}


def test_inference_exports_expected_public_api() -> None:
    """测试推理包公开完整且准确的 API"""
    assert set(inference.__all__) == EXPECTED_EXPORTS
    assert len(inference.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in inference.__all__:
        assert hasattr(inference, name), name
