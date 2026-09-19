"""审计数据净化器测试

验证审计数据的递归脱敏、类型转换、结构限界和循环引用保护。

核心功能：
  - test_sanitize_masks_sensitive_nested_values:
    验证嵌套敏感字段脱敏
  - test_sanitize_converts_non_json_values:
    验证非 JSON 类型转换
  - test_sanitize_converts_structured_values:
    验证结构化对象转换
  - test_sanitize_limits_untrusted_values:
    验证深度、数量和长度限制
  - test_sanitize_handles_circular_values:
    验证循环引用保护
"""

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    timezone,
)
from enum import Enum

import pytest
from pydantic import (
    BaseModel,
    SecretBytes,
    SecretStr,
)

from datamind.audit import sanitizer
from datamind.audit.sanitizer import (
    sanitize_audit_mapping,
    sanitize_audit_value,
)


class SampleStatus(Enum):
    """测试状态枚举"""

    ACTIVE = "active"


class AuditPayload(BaseModel):
    """测试 Pydantic 审计负载"""

    password: SecretStr
    count: int


@dataclass(frozen=True)
class AuditChange:
    """测试 dataclass 审计变更"""

    name: str
    token: str


def test_sanitize_masks_sensitive_nested_values() -> None:
    """测试敏感容器保持结构且所有叶子值均被脱敏"""
    original = {
        "credentials": (
            {"username": "admin", "password": "secret"},
        ),
        "API-Key": "key-value",
        "profile": {"name": "Alice"},
    }

    result = sanitize_audit_value(original)

    assert result == {
        "credentials": [
            {"username": "[REDACTED]", "password": "[REDACTED]"},
        ],
        "API-Key": "[REDACTED]",
        "profile": {"name": "Alice"},
    }
    assert original["credentials"][0]["password"] == "secret"


def test_sanitize_converts_non_json_values() -> None:
    """测试日期、字节和 SecretStr 转换为安全 JSON 值"""
    result = sanitize_audit_value({
        "at": datetime(2026, 7, 27, tzinfo=timezone.utc),
        "raw": b"ab",
        "unsupported": object(),
        "password": SecretStr("secret"),
        "secret_bytes": SecretBytes(b"secret"),
    })

    assert result == {
        "at": "2026-07-27T00:00:00+00:00",
        "raw": "6162",
        "unsupported": "[UNSUPPORTED_TYPE:builtins.object]",
        "password": "[REDACTED]",
        "secret_bytes": "[REDACTED]",
    }


def test_sanitize_converts_structured_values() -> None:
    """测试枚举、Pydantic 模型和 dataclass 转换"""
    result = sanitize_audit_value({
        "status": SampleStatus.ACTIVE,
        "payload": AuditPayload(
            password=SecretStr("secret"),
            count=2,
        ),
        "change": AuditChange(
            name="scorecard",
            token="secret",
        ),
        "date": date(2026, 7, 27),
    })

    assert result == {
        "status": "active",
        "payload": {
            "password": "[REDACTED]",
            "count": 2,
        },
        "change": {
            "name": "scorecard",
            "token": "[REDACTED]",
        },
        "date": "2026-07-27",
    }


def test_sanitize_limits_untrusted_values(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试字符串、键和集合超过限制时被截断"""
    monkeypatch.setattr(sanitizer, "MAX_STRING_LENGTH", 3)
    monkeypatch.setattr(sanitizer, "MAX_ITEMS", 2)
    monkeypatch.setattr(sanitizer, "MAX_KEY_LENGTH", 3)

    result = sanitize_audit_value({
        "text": "abcdef",
        "items": [1, 2, 3],
        "ignored": True,
    })

    assert result == {
        "tex...[TRUNCATED]": "abc...[TRUNCATED]",
        "ite...[TRUNCATED]": [
            1,
            2,
            "[TRUNCATED_ITEMS]",
        ],
        "__truncated__": True,
    }


def test_sanitize_limits_nested_depth(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试嵌套值超过最大深度后停止递归"""
    monkeypatch.setattr(
        sanitizer,
        "MAX_DEPTH",
        2,
    )

    result = sanitize_audit_value({
        "level": {
            "value": "deep",
        },
    })

    assert result == {
        "level": {
            "value": "[MAX_DEPTH]",
        },
    }


def test_sanitize_handles_circular_values() -> None:
    """测试循环引用不会导致无限递归"""
    value: dict[str, object] = {}
    value["self"] = value

    assert sanitize_audit_value(value) == {"self": "[CIRCULAR]"}


def test_sanitize_handles_circular_sequence() -> None:
    """测试序列循环引用不会导致无限递归"""
    value: list[object] = []
    value.append(value)

    assert sanitize_audit_value(value) == [
        "[CIRCULAR]",
    ]


def test_sanitize_mapping_accepts_none() -> None:
    """测试空审计映射保持为空"""
    assert sanitize_audit_mapping(None) is None
