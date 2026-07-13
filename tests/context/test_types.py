# tests/context/test_types.py

"""上下文类型测试

验证 Context TypedDict 的字段定义、可选性和运行时字典行为。

核心功能：
  - test_context_is_typed_dict:
    验证 Context 是 TypedDict 类型
  - test_context_declares_expected_fields:
    验证 Context 声明全部标准上下文字段
  - test_context_fields_are_strings:
    验证 Context 全部字段均为字符串类型
  - test_context_fields_are_optional:
    验证 Context 全部字段均为可选
  - test_context_supports_partial_dictionary:
    验证 Context 支持部分字段字典
  - test_context_supports_complete_dictionary:
    验证 Context 支持完整字段字典
"""

from typing import (
    get_type_hints,
    is_typeddict,
)

from datamind.context.types import Context


EXPECTED_FIELDS = {
    "trace_id",
    "request_id",
    "source",
    "user",
    "ip",
    "hostname",
}


def test_context_is_typed_dict() -> None:
    """测试 Context 是 TypedDict 类型"""
    assert is_typeddict(
        Context
    )


def test_context_declares_expected_fields() -> None:
    """测试 Context 声明全部标准上下文字段"""
    type_hints = get_type_hints(
        Context
    )

    assert set(
        type_hints
    ) == EXPECTED_FIELDS


def test_context_fields_are_strings() -> None:
    """测试 Context 全部字段均为字符串类型"""
    type_hints = get_type_hints(
        Context
    )

    assert all(
        field_type is str
        for field_type in type_hints.values()
    )


def test_context_fields_are_optional() -> None:
    """测试 Context 使用 total=False，全部字段均为可选"""
    required_keys = getattr(
        Context,
        "__required_keys__",
    )
    optional_keys = getattr(
        Context,
        "__optional_keys__",
    )

    assert required_keys == frozenset()
    assert optional_keys == frozenset(
        EXPECTED_FIELDS
    )


def test_context_supports_partial_dictionary() -> None:
    """测试 Context 可以只包含部分上下文字段"""
    context: Context = {
        "trace_id": "trace-123",
        "user": "admin",
    }

    assert context == {
        "trace_id": "trace-123",
        "user": "admin",
    }


def test_context_supports_complete_dictionary() -> None:
    """测试 Context 可以包含全部上下文字段"""
    context: Context = {
        "trace_id": "trace-123",
        "request_id": "req-456",
        "source": "http",
        "user": "admin",
        "ip": "192.168.1.100",
        "hostname": "client-host",
    }

    assert set(context) == EXPECTED_FIELDS
    assert context["source"] == "http"
    assert context["hostname"] == "client-host"
