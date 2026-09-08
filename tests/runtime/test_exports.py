"""模型运行时包公共导出测试

验证模型运行时包公开 API 的完整性和可访问性。

核心功能：
  - test_runtime_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.runtime as runtime


EXPECTED_EXPORTS = {
    "BentoBackend",
    "ControlSnapshot",
    "ExecutionPlan",
    "ExecutionResult",
    "ModelLoader",
    "PredictionExecutor",
    "ReconcileResult",
    "RouteResult",
    "RoutingPlan",
    "RuntimeManager",
    "RuntimeModel",
    "RuntimePresence",
    "RuntimeReconciler",
    "RuntimeRegistry",
    "RuntimeRouter",
    "ShadowDispatcher",
    "ShadowTask",
}


def test_runtime_exports_expected_public_api() -> None:
    """测试运行时包公开完整且准确的 API"""
    assert set(runtime.__all__) == EXPECTED_EXPORTS
    assert len(runtime.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in runtime.__all__:
        assert hasattr(runtime, name), name
