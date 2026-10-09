"""运行时服务接口包公共导出测试.

验证运行时服务接口包公开 API 的完整性和可访问性。

核心功能：
  - test_server_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
  - test_core_functions_document_all_exports:
    验证核心功能完整列出公共 API
  - test_removed_feedback_schema_is_unavailable:
    测试运行服务不再导出业务结果请求模型
"""

import datamind.runtime.server as server
import pytest


EXPECTED_EXPORTS = {
    "BatchPredictRequest",
    "BatchReferenceRequest",
    "ControlRequest",
    "DatamindRuntimeService",
    "DeploymentRequest",
    "PredictRequest",
    "PredictionInstance",
    "ServiceAuthenticationError",
    "ServiceAuthenticationUnavailableError",
    "ServiceAuthorizationError",
    "ServiceDeploymentNotFoundError",
    "ServiceEnvironmentMismatchError",
}


def test_server_exports_expected_public_api() -> None:
    """测试运行时服务接口包公开完整且准确的 API."""
    assert set(server.__all__) == EXPECTED_EXPORTS
    assert len(server.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 __all__ 中声明的对象均可从包级访问."""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "testing",
    )

    for name in server.__all__:
        assert hasattr(server, name), name


def test_core_functions_document_all_exports() -> None:
    """测试模块核心功能完整列出公共 API."""
    documentation = server.__doc__ or ""
    core_functions = documentation.partition("核心功能：")[2].partition(
        "使用示例："
    )[0]

    for name in server.__all__:
        assert f"- {name}:" in core_functions


def test_removed_feedback_schema_is_unavailable() -> None:
    """测试运行服务不再导出业务结果请求模型."""
    from datamind.runtime.server import schemas

    assert not hasattr(schemas, "OutcomeFeedbackRequest")
    assert not hasattr(server.DatamindRuntimeService.inner, "submit_outcome")
