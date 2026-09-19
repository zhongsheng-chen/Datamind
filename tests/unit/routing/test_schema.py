"""路由规则契约测试

验证规范操作符、JSON Schema、示例与运行时规则匹配器保持一致。

核心功能：
  - test_routing_rules_schema_exposes_runtime_contract:
    验证路由规则 Schema 与运行时契约保持一致
  - test_routing_rules_example_is_valid:
    验证路由规则示例通过契约和运行时校验
"""

from datamind.runtime.routing.matcher import RuleMatcher
from datamind.runtime.routing.schema import (
    ROUTING_RULES_EXAMPLE,
    SUPPORTED_ROUTING_MATCH_MODES,
    SUPPORTED_ROUTING_OPERATORS,
    RoutingRules,
)


def test_routing_rules_schema_exposes_runtime_contract() -> None:
    """测试 Schema 和示例使用运行时支持的规范值"""
    schema = RoutingRules.model_json_schema()
    condition_schema = schema["$defs"]["RoutingCondition"]

    assert schema["examples"] == [ROUTING_RULES_EXAMPLE]
    assert set(schema["properties"]["match"]["enum"]) == set(
        SUPPORTED_ROUTING_MATCH_MODES
    )
    assert set(condition_schema["properties"]["op"]["enum"]) == set(
        SUPPORTED_ROUTING_OPERATORS
    )
    assert RuleMatcher.SUPPORTED_MATCH_MODES == set(
        SUPPORTED_ROUTING_MATCH_MODES
    )
    assert RuleMatcher.SUPPORTED_OPERATORS == set(
        SUPPORTED_ROUTING_OPERATORS
    )
    assert set(RuleMatcher.OPERATOR_ALIASES.values()) == set(
        SUPPORTED_ROUTING_OPERATORS
    )


def test_routing_rules_example_is_valid() -> None:
    """测试后端提供的示例同时通过契约和运行时校验"""
    RoutingRules.model_validate(
        ROUTING_RULES_EXAMPLE
    )
    RuleMatcher().validate(
        ROUTING_RULES_EXAMPLE
    )
