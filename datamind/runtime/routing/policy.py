"""运行时路由流量策略

提供启用路由流量占比的校验能力。

核心功能：
  - validate_traffic_allocation: 校验并汇总绝对流量占比
"""

import math
from collections.abc import Iterable
from typing import Any


def validate_traffic_allocation(
        routings: Iterable[Any],
) -> float:
    """校验并返回启用路由的总流量占比"""
    total_ratio = 0.0

    for routing in routings:
        try:
            ratio = float(routing.traffic_ratio)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "路由 traffic_ratio 必须是数值"
            ) from exc

        if not math.isfinite(ratio):
            raise ValueError(
                "路由 traffic_ratio 必须是有限数值"
            )

        if ratio < 0 or ratio > 1:
            raise ValueError(
                "路由 traffic_ratio 必须在 0 到 1 之间"
            )

        total_ratio += ratio

    if total_ratio > 1.0 + 1e-8:
        raise ValueError(
            "启用路由的流量占比总和不能大于 1"
        )

    return total_ratio
