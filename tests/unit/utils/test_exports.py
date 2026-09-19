"""工具包公共导出测试

验证工具包公开 API 的完整性和可访问性。

核心功能：
  - test_utils_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.utils as utils


EXPECTED_EXPORTS = {
    "format_datetime",
    "format_iso_utc",
    "generate_id",
    "generate_random_id",
    "get_host_ip",
    "get_hostname",
    "get_timezone",
    "parse_datetime",
    "to_local",
    "to_utc",
}


def test_utils_exports_expected_public_api() -> None:
    """测试工具包公开完整且准确的 API"""
    assert set(utils.__all__) == EXPECTED_EXPORTS
    assert len(utils.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in utils.__all__:
        assert hasattr(utils, name), name
