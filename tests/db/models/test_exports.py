# tests/db/models/test_exports.py

"""数据库模型包公共导出测试

验证数据库模型包公开 API 的完整性和可访问性。

核心功能：
  - test_model_exports_expected_public_api:
    验证 __all__ 包含完整且准确的模型 API
  - test_all_declared_exports_are_available:
    验证声明的模型均可从包级访问
"""

import datamind.db.models as models


EXPECTED_EXPORTS = {
    "SystemState",
    "User",
    "Role",
    "Grant",
    "Token",
    "Metadata",
    "Version",
    "Deployment",
    "Control",
    "Runtime",
    "Routing",
    "Experiment",
    "Variant",
    "Assignment",
    "Request",
    "Decision",
    "Execution",
    "Outcome",
    "Audit",
    "Artifact",
    "OutboxEvent",
}


def test_model_exports_expected_public_api() -> None:
    """测试模型包公开完整且准确的 API"""
    assert set(models.__all__) == EXPECTED_EXPORTS
    assert len(models.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的模型均可从包级访问"""
    for name in models.__all__:
        assert hasattr(models, name), name
