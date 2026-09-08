"""运行时路由包公共导出测试

验证运行时路由包公开 API 的完整性和可访问性。

核心功能：
  - test_routing_exports_expected_public_api: 验证公共 API 完整准确
  - test_all_declared_exports_are_available: 验证全部声明均可访问
"""

import datamind.runtime.routing as routing


EXPECTED_EXPORTS = {
    "RouteResult",
    "RuleMatcher",
    "RoutingPlan",
    "RuntimeRouter",
    "validate_traffic_allocation",
}


def test_routing_exports_expected_public_api() -> None:
    """测试运行时路由包公开完整且准确的 API"""
    assert set(routing.__all__) == EXPECTED_EXPORTS
    assert len(routing.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可访问"""
    for name in routing.__all__:
        assert hasattr(routing, name), name
