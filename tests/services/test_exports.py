"""业务服务包公共导出测试

验证业务服务包公开 API 的完整性和可访问性。

核心功能：
  - test_service_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.services as services
import datamind.services.errors as service_errors


EXPECTED_EXPORTS = {
    "DashboardService",
    "DeploymentLifecycleService",
    "ExperimentLifecycleService",
    "InitializationService",
    "IdentityService",
    "ModelDeletionService",
    "ModelLifecycleService",
    "ModelRegistrationService",
    "ModelCatalogService",
    "OutcomeService",
    "RuntimeControlService",
    "RoutingLifecycleService",
}

EXPECTED_ERROR_EXPORTS = {
    "AlreadyInitializedError",
    "IdentityConflictError",
    "IdentityError",
    "InitializationError",
    "RoleNotFoundError",
    "UserNotFoundError",
}


def test_service_exports_expected_public_api() -> None:
    """测试业务服务包公开完整且准确的 API"""
    assert set(services.__all__) == EXPECTED_EXPORTS
    assert len(services.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in services.__all__:
        assert hasattr(services, name), name


def test_service_error_exports_expected_public_api() -> None:
    """测试服务异常模块公开完整且准确的 API"""
    assert set(service_errors.__all__) == EXPECTED_ERROR_EXPORTS
    assert len(service_errors.__all__) == len(
        EXPECTED_ERROR_EXPORTS
    )


def test_all_declared_error_exports_are_available() -> None:
    """测试异常模块声明的对象均可访问"""
    for name in service_errors.__all__:
        assert hasattr(
            service_errors,
            name,
        ), name
