"""上下文包公共导出测试.

验证上下文包公开 API 的完整性和可访问性。

核心功能：
  - test_context_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.context as context


EXPECTED_EXPORTS = {
    "Context",
    "set_context",
    "get_context",
    "clear_context",
    "update_context",
    "context_scope",
    "generate_trace_id",
    "is_valid_trace_id",
}


def test_context_exports_expected_public_api() -> None:
    """测试上下文包公开完整且准确的 API."""
    assert set(context.__all__) == EXPECTED_EXPORTS
    assert len(context.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问."""
    for name in context.__all__:
        assert hasattr(context, name), name
