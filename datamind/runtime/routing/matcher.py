# datamind/runtime/routing/matcher.py

"""规则匹配器

提供规则配置的校验与匹配能力，用于判断请求 payload 是否满足指定 rules。

核心功能：
  - match: 判断 payload 是否匹配 rules
  - validate: 校验 rules 结构是否合法

说明：
  - match 支持 all / any，分别表示全部条件满足 / 任一条件满足
  - field 支持点号路径，例如 annual_income、features.age、request.features.age
  - bucket_key、customer_id 等配置属于路由元信息，不作为过滤条件

支持操作符：
  - 比较：eq / ne / gt / gte / lt / lte
  - 集合：in / not_in
  - 范围：between
  - 存在性：exists / missing / is_null / not_null
  - 字符串：contains / not_contains / startswith / endswith / regex

规则格式：
  - 多条件：{"match": "all", "conditions": [{"field": "age", "op": "gte", "value": 18}]}
  - 单条件：{"field": "age", "op": "gte", "value": 18}

使用示例：
  from datamind.runtime.routing import RuleMatcher

  matcher = RuleMatcher()

  payload = {
      "features": {
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      }
  }

  rules = {
      "match": "all",
      "conditions": [
          {
              "field": "features.annual_income",
              "op": "gte",
              "value": 100000,
          },
          {
              "field": "features.age",
              "op": "eq",
              "value": 35,
          },
      ],
  }

  matcher.validate(rules)

  if matcher.match(payload=payload, rules=rules):
      print("命中规则")
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard


class _Missing:
    """缺失值标记"""


MISSING = _Missing()


class RuleMatcher:
    """规则匹配器"""

    MATCH_ALL = "all"
    MATCH_ANY = "any"

    SUPPORTED_MATCH_MODES = {
        MATCH_ALL,
        MATCH_ANY,
    }

    OPERATOR_ALIASES = {
        "=": "eq",
        "==": "eq",
        "eq": "eq",
        "equals": "eq",

        "!=": "ne",
        "<>": "ne",
        "ne": "ne",
        "not_eq": "ne",
        "not_equals": "ne",

        ">": "gt",
        "gt": "gt",

        ">=": "gte",
        "gte": "gte",
        "ge": "gte",

        "<": "lt",
        "lt": "lt",

        "<=": "lte",
        "lte": "lte",
        "le": "lte",

        "in": "in",

        "not_in": "not_in",
        "not-in": "not_in",
        "not in": "not_in",

        "between": "between",
        "range": "between",

        "exists": "exists",
        "missing": "missing",

        "is_null": "is_null",
        "is-null": "is_null",
        "is null": "is_null",

        "not_null": "not_null",
        "not-null": "not_null",
        "not null": "not_null",

        "contains": "contains",

        "not_contains": "not_contains",
        "not-contains": "not_contains",
        "not contains": "not_contains",

        "startswith": "startswith",
        "starts_with": "startswith",
        "starts-with": "startswith",
        "prefix": "startswith",

        "endswith": "endswith",
        "ends_with": "endswith",
        "ends-with": "endswith",
        "suffix": "endswith",

        "regex": "regex",
    }

    SUPPORTED_OPERATORS = set(OPERATOR_ALIASES.values())

    # 路由元信息配置，不作为条件规则处理。
    METADATA_ONLY_KEYS = {
        "bucket_key",
        "bucket_range",
        "customer_id",
        "hash_salt",
        "salt",
        "description",
        "note",
        "version",
    }

    def match(
            self,
            *,
            payload: Mapping[str, Any] | None,
            rules: Mapping[str, Any] | None,
    ) -> bool:
        """判断 payload 是否匹配 rules

        参数：
            payload: 请求数据，可以是完整请求对象，也可以直接是 features 字典
            rules: 规则配置

        返回：
            True 表示匹配，False 表示不匹配

        异常：
            ValueError: rules 结构不合法
        """
        if not rules:
            return True

        if not isinstance(rules, Mapping):
            raise ValueError("rules 必须是 JSON 对象")

        conditions = self._extract_conditions(
            rules
        )

        if not conditions:
            return True

        match_mode = str(
            rules.get("match", self.MATCH_ALL)
        ).strip().lower()

        if match_mode not in self.SUPPORTED_MATCH_MODES:
            raise ValueError(
                "rules.match 仅支持 all / any，"
                f"当前值: {match_mode}"
            )

        normalized_payload: Mapping[str, Any] = payload or {}

        results = [
            self._match_condition(
                payload=normalized_payload,
                condition=condition,
            )
            for condition in conditions
        ]

        if match_mode == self.MATCH_ANY:
            return any(results)

        return all(results)

    def validate(
            self,
            rules: Mapping[str, Any] | None,
    ) -> None:
        """校验 rules 结构是否合法

        参数：
            rules: 规则配置

        异常：
            ValueError: rules 结构不合法
        """
        if not rules:
            return

        if not isinstance(rules, Mapping):
            raise ValueError("rules 必须是 JSON 对象")

        match_mode = str(
            rules.get("match", self.MATCH_ALL)
        ).strip().lower()

        if match_mode not in self.SUPPORTED_MATCH_MODES:
            raise ValueError(
                "rules.match 仅支持 all / any，"
                f"当前值: {match_mode}"
            )

        conditions = self._extract_conditions(
            rules
        )

        for condition in conditions:
            self._validate_condition(
                condition
            )

    def _extract_conditions(
            self,
            rules: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        """从 rules 中提取条件列表"""
        if "conditions" in rules:
            raw_conditions = rules.get("conditions")

            if raw_conditions is None:
                return []

            if not self._is_non_string_sequence(raw_conditions):
                raise ValueError("rules.conditions 必须是数组")

            conditions = []

            for item in raw_conditions:
                if not isinstance(item, Mapping):
                    raise ValueError("rules.conditions 中每一项必须是对象")

                self._validate_condition(
                    item
                )
                conditions.append(item)

            return conditions

        if "field" in rules or "path" in rules:
            self._validate_condition(
                rules
            )
            return [rules]

        if set(rules.keys()).issubset(self.METADATA_ONLY_KEYS):
            return []

        unknown_keys = ", ".join(
            sorted(str(key) for key in rules)
        )
        raise ValueError(
            "rules 结构无效，必须提供 conditions、"
            "field/path 或受支持的路由元信息，"
            f"当前字段: {unknown_keys}"
        )

    def _validate_condition(
            self,
            condition: Mapping[str, Any],
    ) -> None:
        """校验单个条件结构"""
        field = condition.get(
            "field",
            condition.get("path"),
        )
        operator = condition.get(
            "op",
            condition.get("operator"),
        )

        if not field:
            raise ValueError("condition 缺少 field")

        if not isinstance(field, str):
            raise ValueError("condition.field 必须是字符串")

        if not operator:
            raise ValueError("condition 缺少 op")

        op = self._normalize_operator(
            operator
        )

        if op not in self.SUPPORTED_OPERATORS:
            raise ValueError(f"不支持的 op: {operator}")

        if op in {
            "exists",
            "missing",
            "is_null",
            "not_null",
        }:
            return

        if "value" not in condition:
            raise ValueError(
                "condition 缺少 value，"
                f"field={field}, op={operator}"
            )

        value = condition.get("value")

        if op in {"in", "not_in"}:
            if not self._is_non_string_sequence(value):
                raise ValueError(
                    "condition.value 在 in/not_in 下必须是数组"
                )

        if op == "between":
            if not self._is_non_string_sequence(value) or len(value) != 2:
                raise ValueError(
                    "condition.value 在 between 下必须是长度为 2 的数组"
                )

    def _match_condition(
            self,
            *,
            payload: Mapping[str, Any],
            condition: Mapping[str, Any],
    ) -> bool:
        """判断单个条件是否匹配"""
        self._validate_condition(
            condition
        )

        field = condition.get(
            "field",
            condition.get("path"),
        )
        operator = condition.get(
            "op",
            condition.get("operator"),
        )
        expected = condition.get("value")
        negate = bool(
            condition.get("negate", False)
        )

        actual = self._get_payload_value(
            payload=payload,
            field=field,
        )

        matched = self._compare(
            actual=actual,
            operator=operator,
            expected=expected,
        )

        if negate:
            return not matched

        return matched

    def _get_payload_value(
            self,
            *,
            payload: Mapping[str, Any],
            field: str,
    ) -> Any:
        """从 payload 中按字段路径取值"""
        candidate_paths = self._candidate_paths(
            field
        )

        for path in candidate_paths:
            value = self._get_by_path(
                payload,
                path,
            )

            if value is not MISSING:
                return value

        return MISSING

    def _candidate_paths(
            self,
            field: str,
    ) -> list[str]:
        """生成兼容不同 payload 结构的候选字段路径"""
        paths = [
            field,
        ]

        if field.startswith("features."):
            stripped = field.removeprefix("features.")

            paths.extend(
                [
                    stripped,
                    f"request.features.{stripped}",
                ]
            )

        elif field.startswith("request.features."):
            stripped = field.removeprefix("request.features.")

            paths.extend(
                [
                    stripped,
                    f"features.{stripped}",
                ]
            )

        else:
            paths.extend(
                [
                    f"features.{field}",
                    f"request.features.{field}",
                    f"request.{field}",
                ]
            )

        return self._deduplicate(
            paths
        )

    def _get_by_path(
            self,
            obj: Any,
            path: str,
    ) -> Any:
        """按点号路径从 dict/list 中取值"""
        current = obj

        for part in path.split("."):
            if part == "":
                return MISSING

            if isinstance(current, Mapping):
                if part not in current:
                    return MISSING

                current = current[part]
                continue

            if self._is_non_string_sequence(current):
                try:
                    index = int(part)
                except ValueError:
                    return MISSING

                if index < 0 or index >= len(current):
                    return MISSING

                current = current[index]
                continue

            return MISSING

        return current

    def _compare(
            self,
            *,
            actual: Any,
            operator: Any,
            expected: Any,
    ) -> bool:
        """按操作符比较实际值和期望值"""
        op = self._normalize_operator(
            operator
        )

        if op == "exists":
            target = True if expected is None else bool(expected)
            result = actual is not MISSING and actual is not None
            return result is target

        if op == "missing":
            target = True if expected is None else bool(expected)
            result = actual is MISSING or actual is None
            return result is target

        if op == "is_null":
            return actual is None

        if op == "not_null":
            return actual is not MISSING and actual is not None

        if actual is MISSING:
            return False

        if op == "eq":
            return self._loose_equal(
                actual,
                expected,
            )

        if op == "ne":
            return not self._loose_equal(
                actual,
                expected,
            )

        if op in {"gt", "gte", "lt", "lte"}:
            actual_number = self._to_number(
                actual
            )
            expected_number = self._to_number(
                expected
            )

            if actual_number is None or expected_number is None:
                return False

            if op == "gt":
                return actual_number > expected_number

            if op == "gte":
                return actual_number >= expected_number

            if op == "lt":
                return actual_number < expected_number

            return actual_number <= expected_number

        if op == "between":
            if not self._is_non_string_sequence(expected) or len(expected) != 2:
                return False

            actual_number = self._to_number(
                actual
            )
            lower = self._to_number(
                expected[0]
            )
            upper = self._to_number(
                expected[1]
            )

            if actual_number is None or lower is None or upper is None:
                return False

            return lower <= actual_number <= upper

        if op == "in":
            if not self._is_non_string_sequence(expected):
                return False

            return self._value_in(
                actual=actual,
                expected=expected,
            )

        if op == "not_in":
            if not self._is_non_string_sequence(expected):
                return False

            return not self._value_in(
                actual=actual,
                expected=expected,
            )

        if op == "contains":
            return self._contains(
                actual=actual,
                expected=expected,
            )

        if op == "not_contains":
            return not self._contains(
                actual=actual,
                expected=expected,
            )

        if op == "startswith":
            return str(actual).startswith(
                str(expected)
            )

        if op == "endswith":
            return str(actual).endswith(
                str(expected)
            )

        if op == "regex":
            try:
                return re.search(
                    str(expected),
                    str(actual),
                ) is not None
            except re.error:
                return False

        raise ValueError(f"不支持的 op: {operator}")

    def _normalize_operator(
            self,
            operator: Any,
    ) -> str:
        """归一化操作符"""
        key = str(operator).strip().lower()

        if key not in self.OPERATOR_ALIASES:
            raise ValueError(f"不支持的 op: {operator}")

        return self.OPERATOR_ALIASES[key]

    def _loose_equal(
            self,
            actual: Any,
            expected: Any,
    ) -> bool:
        """宽松等值比较"""
        actual_number = self._to_number(
            actual
        )
        expected_number = self._to_number(
            expected
        )

        if actual_number is not None and expected_number is not None:
            return actual_number == expected_number

        return actual == expected

    @staticmethod
    def _to_number(
            value: Any,
    ) -> float | None:
        """尝试转换为数字"""
        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            text = value.strip()

            if text == "":
                return None

            try:
                return float(text)
            except ValueError:
                return None

        return None

    def _value_in(
            self,
            *,
            actual: Any,
            expected: Sequence[Any],
    ) -> bool:
        """判断 actual 是否在 expected 中"""
        if self._is_non_string_sequence(actual):
            return any(
                self._loose_equal(item, option)
                for item in actual
                for option in expected
            )

        return any(
            self._loose_equal(actual, option)
            for option in expected
        )

    def _contains(
            self,
            *,
            actual: Any,
            expected: Any,
    ) -> bool:
        """判断 actual 是否包含 expected"""
        if isinstance(actual, str):
            return str(expected) in actual

        if isinstance(actual, Mapping):
            return expected in actual

        if self._is_non_string_sequence(actual):
            return any(
                self._loose_equal(item, expected)
                for item in actual
            )

        return False

    @staticmethod
    def _is_non_string_sequence(
            value: Any,
    ) -> TypeGuard[Sequence[Any]]:
        """判断是否是非字符串序列"""
        return isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        )

    @staticmethod
    def _deduplicate(
            values: Sequence[str],
    ) -> list[str]:
        """按顺序去重"""
        result = []
        seen = set()

        for value in values:
            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result
