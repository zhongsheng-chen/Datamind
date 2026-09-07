# tests/db/repositories/test_exports.py

"""数据库仓储包公共导出测试

验证数据库仓储包公开 API 的完整性和可访问性。

核心功能：
  - test_repository_exports_expected_public_api:
    验证 __all__ 包含完整且准确的仓储 API
  - test_all_declared_exports_are_available:
    验证声明的仓储对象均可从包级访问
"""

import datamind.db.repositories as repositories


EXPECTED_EXPORTS = {
    "BaseRepository",
    "SystemStateRepository",
    "UserPatch",
    "UserRepository",
    "RolePatch",
    "RoleRepository",
    "GrantRepository",
    "TokenRepository",
    "MetadataPatch",
    "MetadataRepository",
    "VersionPatch",
    "VersionRepository",
    "ScorecardRepository",
    "DeploymentPatch",
    "DeploymentRepository",
    "DashboardRepository",
    "ControlRepository",
    "RuntimePatch",
    "RuntimeRepository",
    "RoutingPatch",
    "RoutingRepository",
    "ExperimentPatch",
    "ExperimentRepository",
    "VariantPatch",
    "VariantRepository",
    "AssignmentRepository",
    "RequestRepository",
    "DecisionRepository",
    "ExecutionRepository",
    "OutcomePatch",
    "OutcomeRepository",
    "AuditRepository",
    "ArtifactRepository",
    "OutboxRepository",
}


def test_repository_exports_expected_public_api() -> None:
    """测试仓储包公开完整且准确的 API"""
    assert set(repositories.__all__) == EXPECTED_EXPORTS
    assert len(repositories.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的仓储对象均可从包级访问"""
    for name in repositories.__all__:
        assert hasattr(repositories, name), name
