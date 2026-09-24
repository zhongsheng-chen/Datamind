"""审计存储端包级导出测试.

验证审计存储端包级公共 API 的完整性和可访问性。

核心功能：
  - test_sink_exports_are_explicit:
    验证公开 API 列表
  - test_sink_exports_resolve:
    验证公开符号均可访问
"""

import datamind.audit.sinks as sinks


def test_sink_exports_are_explicit() -> None:
    """测试存储端公开 API 列表稳定."""
    assert sinks.__all__ == [
        "AuditSink",
        "DatabaseAuditSink",
    ]


def test_sink_exports_resolve() -> None:
    """测试存储端公开符号均可解析."""
    for name in sinks.__all__:
        assert getattr(
            sinks,
            name,
        ) is not None
