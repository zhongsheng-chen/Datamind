"""上下文键测试

验证标准上下文键的名称、唯一性、完整性和固定顺序。

核心功能：
  - test_context_key_values:
    验证上下文键使用预期字段名
  - test_context_keys_are_unique:
    验证所有标准上下文键互不重复
  - test_all_keys_contains_every_standard_key:
    验证 ALL_KEYS 包含全部标准上下文键
  - test_all_keys_preserves_standard_order:
    验证 ALL_KEYS 保持标准上下文键顺序
"""

from datamind.context.keys import (
    ALL_KEYS,
    HOSTNAME,
    IP,
    REQUEST_ID,
    SOURCE,
    TRACE_ID,
    USER,
)


EXPECTED_KEYS = (
    TRACE_ID,
    REQUEST_ID,
    SOURCE,
    USER,
    IP,
    HOSTNAME,
)


def test_context_key_values() -> None:
    """测试上下文键使用预期字段名"""
    assert TRACE_ID == "trace_id"
    assert REQUEST_ID == "request_id"
    assert SOURCE == "source"
    assert USER == "user"
    assert IP == "ip"
    assert HOSTNAME == "hostname"


def test_context_keys_are_unique() -> None:
    """测试所有标准上下文键互不重复"""
    assert len(
        EXPECTED_KEYS
    ) == len(
        set(
            EXPECTED_KEYS
        )
    )


def test_all_keys_contains_every_standard_key() -> None:
    """测试 ALL_KEYS 包含全部标准上下文键"""
    assert set(
        ALL_KEYS
    ) == {
        "trace_id",
        "request_id",
        "source",
        "user",
        "ip",
        "hostname",
    }


def test_all_keys_preserves_standard_order() -> None:
    """测试 ALL_KEYS 保持标准上下文键顺序"""
    assert ALL_KEYS == EXPECTED_KEYS
