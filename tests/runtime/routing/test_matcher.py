# tests/runtime/routing/test_matcher.py

"""路由规则匹配器测试

验证规则结构校验、字段解析、组合条件和操作符匹配行为。

核心功能：
  - 验证空规则及路由元信息规则
  - 验证非法规则结构被拒绝
  - 验证 all、any 和 negate 组合条件
  - 验证嵌套字段和数组索引解析
  - 验证比较、集合、范围、存在性和字符串操作符
"""

from typing import Any

import pytest

from datamind.runtime.routing import RuleMatcher


def match(
        *,
        value: Any,
        operator: str,
        expected: Any = None,
        include_value: bool = True,
) -> bool:
    """执行单条件规则匹配"""
    condition: dict[str, Any] = {
        "field": "value",
        "op": operator,
    }

    if include_value:
        condition["value"] = expected

    return RuleMatcher().match(
        payload={"value": value},
        rules=condition,
    )


def test_empty_rules_match() -> None:
    """测试空规则默认命中"""
    matcher = RuleMatcher()

    assert matcher.match(
        payload=None,
        rules=None,
    ) is True
    assert matcher.match(
        payload={},
        rules={},
    ) is True


def test_match_rejects_unknown_rule_shape() -> None:
    """测试未知规则结构不会默认命中"""
    matcher = RuleMatcher()
    rules = {
        "conditons": [
            {"field": "age", "op": "gte", "value": 18}
        ]
    }

    with pytest.raises(ValueError, match="rules 结构无效"):
        matcher.validate(rules)

    with pytest.raises(ValueError, match="rules 结构无效"):
        matcher.match(payload={"age": 35}, rules=rules)


def test_metadata_only_rules_match() -> None:
    """测试受支持的路由元信息不作为过滤条件"""
    assert RuleMatcher().match(
        payload={},
        rules={"bucket_key": "customer_id", "salt": "stable"},
    ) is True


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        ({"match": "some", "conditions": []}, "rules.match"),
        ({"conditions": "invalid"}, "rules.conditions"),
        ({"conditions": ["invalid"]}, "每一项必须是对象"),
        ({"field": "age"}, "缺少 op"),
        (
            {"conditions": [{"op": "eq", "value": 18}]},
            "缺少 field",
        ),
        ({"field": 1, "op": "eq", "value": 1}, "field 必须是字符串"),
        ({"field": "age", "op": "unknown", "value": 18}, "不支持的 op"),
        ({"field": "age", "op": "eq"}, "缺少 value"),
        ({"field": "age", "op": "in", "value": "18"}, "必须是数组"),
        ({"field": "age", "op": "between", "value": [18]}, "长度为 2"),
    ],
)
def test_validate_rejects_invalid_rules(
        rules: dict[str, Any],
        message: str,
) -> None:
    """测试规则校验拒绝非法结构"""
    with pytest.raises(
            ValueError,
            match=message,
    ):
        RuleMatcher().validate(rules)


def test_validate_accepts_empty_conditions() -> None:
    """测试空条件数组是合法的无过滤规则"""
    matcher = RuleMatcher()

    matcher.validate(None)
    matcher.validate({"conditions": None})

    assert matcher.match(
        payload={},
        rules={"conditions": None},
    ) is True


def test_match_supports_all_any_and_negate() -> None:
    """测试组合模式和条件取反"""
    payload = {
        "age": 35,
        "annual_income": 120000,
    }
    conditions = [
        {"field": "age", "op": "gte", "value": 18},
        {
            "field": "annual_income",
            "op": "lt",
            "value": 100000,
            "negate": True,
        },
    ]
    matcher = RuleMatcher()

    assert matcher.match(
        payload=payload,
        rules={"match": "all", "conditions": conditions},
    ) is True
    assert matcher.match(
        payload=payload,
        rules={
            "match": "any",
            "conditions": [
                {"field": "age", "op": "lt", "value": 18},
                conditions[1],
            ],
        },
    ) is True


@pytest.mark.parametrize(
    "field",
    [
        "age",
        "features.age",
        "request.features.age",
    ],
)
def test_match_resolves_compatible_feature_paths(
        field: str,
) -> None:
    """测试兼容不同层级的特征字段路径"""
    assert RuleMatcher().match(
        payload={
            "request": {
                "features": {
                    "age": 35,
                },
            },
        },
        rules={"field": field, "op": "eq", "value": 35},
    ) is True


def test_match_resolves_array_index_and_missing_path() -> None:
    """测试数组索引和缺失字段路径"""
    matcher = RuleMatcher()
    payload = {
        "values": [10, 20],
    }

    assert matcher.match(
        payload=payload,
        rules={"path": "values.1", "operator": "eq", "value": 20},
    ) is True
    assert matcher.match(
        payload=payload,
        rules={"path": "values.x", "operator": "eq", "value": 20},
    ) is False
    assert matcher.match(
        payload=payload,
        rules={"path": "values.9", "operator": "eq", "value": 20},
    ) is False


@pytest.mark.parametrize(
    ("value", "operator", "expected", "matched"),
    [
        ("35", "=", 35, True),
        (35, "!=", 36, True),
        (35, ">", 34, True),
        (35, ">=", 35, True),
        (35, "<", 36, True),
        (35, "<=", 35, True),
        (35, "between", [18, 60], True),
        (35, "between", [36, 60], False),
        ("gold", "in", ["silver", "gold"], True),
        (["gold", "vip"], "in", ["vip"], True),
        ("basic", "not_in", ["gold", "vip"], True),
        ("credit-risk", "contains", "risk", True),
        (["risk", "score"], "contains", "score", True),
        ({"score": 720}, "contains", "score", True),
        (10, "contains", 1, False),
        ("credit-risk", "not_contains", "fraud", True),
        ("credit-risk", "startswith", "credit", True),
        ("credit-risk", "endswith", "risk", True),
        ("risk-2026", "regex", r"^risk-\d+$", True),
        ("risk-2026", "regex", "[", False),
        (True, "gt", 0, False),
        ("invalid", "gt", 0, False),
    ],
)
def test_match_supports_value_operators(
        value: Any,
        operator: str,
        expected: Any,
        matched: bool,
) -> None:
    """测试值比较操作符"""
    assert match(
        value=value,
        operator=operator,
        expected=expected,
    ) is matched


def test_match_supports_existence_operators() -> None:
    """测试字段存在性和空值操作符"""
    matcher = RuleMatcher()
    payload = {
        "value": None,
    }

    assert matcher.match(
        payload=payload,
        rules={"field": "value", "op": "is_null"},
    ) is True
    assert matcher.match(
        payload=payload,
        rules={"field": "value", "op": "not_null"},
    ) is False
    assert matcher.match(
        payload=payload,
        rules={"field": "missing", "op": "missing"},
    ) is True
    assert matcher.match(
        payload={"value": 0},
        rules={"field": "value", "op": "exists"},
    ) is True
    assert matcher.match(
        payload={"value": 0},
        rules={"field": "value", "op": "exists", "value": False},
    ) is False
