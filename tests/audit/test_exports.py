"""审计组件包级导出测试

验证审计组件包级公共 API 的完整性和可访问性。

核心功能：
  - test_audit_exports_are_explicit:
    验证 __all__ 包含完整且明确的公共 API
  - test_audit_exports_resolve:
    验证声明的公共符号均可从包级访问
"""

import datamind.audit as audit_package


def test_audit_exports_are_explicit() -> None:
    """测试公开 API 列表稳定"""
    assert audit_package.__all__ == [
        "AuditFailureMode",
        "AuditRecorder",
        "AuditResult",
        "AuditService",
        "audit",
    ]


def test_audit_exports_resolve() -> None:
    """测试公开符号均可解析"""
    for name in audit_package.__all__:
        assert getattr(audit_package, name) is not None
