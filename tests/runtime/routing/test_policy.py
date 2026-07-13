# tests/runtime/routing/test_policy.py

"""运行时路由流量策略测试

验证路由流量占比使用绝对比例且总和不超过 1。

核心功能：
  - test_validate_traffic_allocation: 验证返回有效路由总占比
  - test_validate_traffic_allocation_rejects_invalid_ratio: 验证拒绝非法单项占比
  - test_validate_traffic_allocation_rejects_invalid_total: 验证拒绝超过全部流量的配置
"""

from types import SimpleNamespace

import pytest

from datamind.runtime.routing import validate_traffic_allocation


def test_validate_traffic_allocation() -> None:
    """测试返回有效路由总占比"""
    total = validate_traffic_allocation([
        SimpleNamespace(traffic_ratio=0.1),
        SimpleNamespace(traffic_ratio=0.2),
    ])

    assert total == pytest.approx(0.3)


def test_validate_traffic_allocation_rejects_invalid_total() -> None:
    """测试拒绝超过全部流量的配置"""
    with pytest.raises(ValueError, match="总和不能大于 1"):
        validate_traffic_allocation([
            SimpleNamespace(traffic_ratio=0.6),
            SimpleNamespace(traffic_ratio=0.6),
        ])


@pytest.mark.parametrize(
    ("ratio", "message"),
    [
        (None, "必须是数值"),
        ("invalid", "必须是数值"),
        (float("inf"), "必须是有限数值"),
        (float("nan"), "必须是有限数值"),
        (-0.1, "必须在 0 到 1 之间"),
        (1.1, "必须在 0 到 1 之间"),
    ],
)
def test_validate_traffic_allocation_rejects_invalid_ratio(
        ratio: object,
        message: str,
) -> None:
    """测试拒绝非法单项流量占比"""
    with pytest.raises(
            ValueError,
            match=message,
    ):
        validate_traffic_allocation([
            SimpleNamespace(traffic_ratio=ratio),
        ])
