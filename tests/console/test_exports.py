# tests/console/test_exports.py

"""内网管理控制台公共导出测试

验证控制台包公开 API 的完整性和可访问性。

核心功能：
  - test_console_exports_expected_public_api: 验证控制台公共 API
"""

import datamind.console as console


EXPECTED_EXPORTS = {
    "console_app",
    "DatamindConsoleService",
}


def test_console_exports_expected_public_api() -> None:
    """测试控制台包公开完整且准确的 API"""
    assert set(console.__all__) == EXPECTED_EXPORTS

    for name in console.__all__:
        assert hasattr(
            console,
            name,
        ), name
