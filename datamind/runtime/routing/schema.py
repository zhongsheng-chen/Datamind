"""路由规则契约

集中定义路由规则的规范操作符、JSON Schema 和示例，供运行时校验器与
管理控制台共同使用。

核心功能：
  - RoutingCondition: 规范的单条路由条件
  - RoutingRules: 规范的多条件路由规则
  - ROUTING_RULES_EXAMPLE: 控制台展示和下载的规则示例
"""

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field


RoutingOperator = Literal[
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "between",
    "exists",
    "missing",
    "is_null",
    "not_null",
    "contains",
    "not_contains",
    "startswith",
    "endswith",
    "regex",
]

RoutingMatchMode = Literal["all", "any"]

SUPPORTED_ROUTING_OPERATORS = frozenset(
    get_args(RoutingOperator)
)
SUPPORTED_ROUTING_MATCH_MODES = frozenset(
    get_args(RoutingMatchMode)
)

ROUTING_RULES_EXAMPLE: dict[str, Any] = {
    "match": "all",
    "conditions": [
        {
            "field": "features.credit_utilization_ratio",
            "op": "gte",
            "value": 0.7,
        },
    ],
}


class RoutingCondition(BaseModel):
    """规范的单条路由条件"""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    op: RoutingOperator
    value: Any = None
    negate: bool = False


class RoutingRules(BaseModel):
    """规范的多条件路由规则"""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [ROUTING_RULES_EXAMPLE],
        },
    )

    match: RoutingMatchMode = "all"
    conditions: list[RoutingCondition]
