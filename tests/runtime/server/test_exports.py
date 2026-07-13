# tests/runtime/server/test_exports.py

"""运行时服务接口包公共导出测试

验证运行时服务接口包公开 API 的完整性和可访问性。

核心功能：
  - test_server_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.runtime.server as server
import pytest


EXPECTED_EXPORTS = {
    "BatchPredictRequest",
    "ControlRequest",
    "DatamindRuntimeService",
    "DeploymentRequest",
    "OutcomeFeedbackRequest",
    "PredictRequest",
    "ServiceAuthenticationError",
    "ServiceAuthenticationUnavailableError",
    "ServiceAuthorizationError",
    "ServiceDeploymentNotFoundError",
    "ServiceEnvironmentMismatchError",
}


def test_server_exports_expected_public_api() -> None:
    """测试运行时服务接口包公开完整且准确的 API"""
    assert set(server.__all__) == EXPECTED_EXPORTS
    assert len(server.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "testing",
    )

    for name in server.__all__:
        assert hasattr(server, name), name
