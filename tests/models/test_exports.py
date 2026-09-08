"""模型包公共导出测试

验证模型包公开 API 的完整性和可访问性。

核心功能：
  - test_model_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import pytest

import datamind.models as models


EXPECTED_EXPORTS = {
    "ArtifactError",
    "AssignmentStrategy",
    "BackendError",
    "BaseEnum",
    "DecisionStrategy",
    "DeploymentRole",
    "DeploymentError",
    "DeploymentNotFoundError",
    "DeploymentStatus",
    "ExperimentError",
    "ExperimentStatus",
    "ExperimentVariantStatus",
    "ExecutionStatus",
    "ExecutionType",
    "InvalidDeploymentStateError",
    "InvalidExperimentConfigError",
    "InvalidExperimentStateError",
    "InvalidModelStateError",
    "MetadataStatus",
    "ModelAlreadyExistsError",
    "ModelArtifactLoader",
    "ModelArtifactRegister",
    "ModelError",
    "ModelGuard",
    "ModelNotFoundError",
    "ModelResolver",
    "RuntimeControlStatus",
    "RuntimeRouteError",
    "RolloutType",
    "SchemaExtractor",
    "VersionNotFoundError",
    "VersionStatus",
}


def test_model_exports_expected_public_api() -> None:
    """测试模型包公开完整且准确的 API"""
    assert set(models.__all__) == EXPECTED_EXPORTS
    assert len(models.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in models.__all__:
        assert hasattr(models, name), name


def test_module_dir_contains_declared_exports() -> None:
    """测试模块属性列表包含全部公共导出"""
    module_attributes = dir(models)

    assert set(models.__all__).issubset(
        module_attributes
    )


def test_unknown_export_raises_attribute_error() -> None:
    """测试访问未声明的包级对象时抛出异常"""
    with pytest.raises(
        AttributeError,
        match="has no attribute 'unknown_export'",
    ):
        getattr(
            models,
            "unknown_export",
        )
