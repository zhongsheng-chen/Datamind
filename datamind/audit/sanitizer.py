"""审计数据净化器.

将任意 Python 值转换为可安全写入 JSON 的有限结构，
并递归脱敏敏感字段。

核心功能：
  - sanitize_audit_value: 净化单个审计字段
  - sanitize_audit_mapping: 净化审计上下文映射

使用示例：
  from datamind.audit.sanitizer import sanitize_audit_value

  sanitized = sanitize_audit_value(
      {
          "password": "secret",
          "name": "scorecard",
      }
  )
"""

from collections.abc import (
    Mapping,
    Sequence,
)
from dataclasses import (
    asdict,
    is_dataclass,
)
from datetime import (
    date,
    datetime,
)
from enum import Enum
from typing import (
    Any,
    Final,
)

from pydantic import (
    BaseModel,
    SecretBytes,
    SecretStr,
)

REDACTED: Final[str] = "[REDACTED]"
MAX_DEPTH: Final[int] = 8
MAX_ITEMS: Final[int] = 100
MAX_KEY_LENGTH: Final[int] = 256
MAX_STRING_LENGTH: Final[int] = 4096

_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "card_number",
        "client_secret",
        "credential",
        "credentials",
        "cvv",
        "id_number",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    }
)


def _is_sensitive_key(
        key: str,
) -> bool:
    """判断字段名是否包含敏感语义."""
    normalized = (
        key.strip()
        .lower()
        .replace(
            "-",
            "_",
        )
    )

    return any(
        item in normalized
        for item in _SENSITIVE_KEYS
    )


def _truncate(
        value: str,
) -> str:
    """限制审计字符串长度."""
    if len(value) <= MAX_STRING_LENGTH:
        return value

    return (
        value[:MAX_STRING_LENGTH]
        + "...[TRUNCATED]"
    )


def sanitize_audit_value(
        value: Any,
        *,
        _depth: int = 0,
        _force_redact: bool = False,
        _seen: set[int] | None = None,
) -> Any:
    """转换、限界并脱敏审计值，且不修改输入对象."""
    if _depth >= MAX_DEPTH:
        return "[MAX_DEPTH]"

    if isinstance(value, (SecretStr, SecretBytes)):
        return REDACTED

    if value is None or isinstance(value, (bool, int, float)):
        return REDACTED if _force_redact else value

    if isinstance(value, str):
        return REDACTED if _force_redact else _truncate(value)

    if isinstance(value, bytes):
        return REDACTED if _force_redact else _truncate(value.hex())

    if isinstance(value, Enum):
        return sanitize_audit_value(
            value.value,
            _depth=_depth,
            _force_redact=_force_redact,
            _seen=_seen,
        )

    if isinstance(value, (datetime, date)):
        return REDACTED if _force_redact else value.isoformat()

    if isinstance(value, BaseModel):
        value = value.model_dump(
            mode="python"
        )
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(
            value
        )

    seen = _seen if _seen is not None else set()
    identity = id(value)

    if isinstance(value, Mapping):
        if identity in seen:
            return "[CIRCULAR]"

        seen.add(
            identity
        )

        try:
            mapping_result: dict[str, Any] = {}

            for index, (key, item) in enumerate(
                    value.items()
            ):
                if index >= MAX_ITEMS:
                    mapping_result["__truncated__"] = True
                    break

                raw_key = str(key)
                key_text = (
                    raw_key
                    if len(raw_key) <= MAX_KEY_LENGTH
                    else (
                        raw_key[:MAX_KEY_LENGTH]
                        + "...[TRUNCATED]"
                    )
                )
                mapping_result[key_text] = sanitize_audit_value(
                    item,
                    _depth=_depth + 1,
                    _force_redact=(
                        _force_redact or _is_sensitive_key(key_text)
                    ),
                    _seen=seen,
                )

            return mapping_result
        finally:
            seen.remove(
                identity
            )

    if isinstance(value, Sequence) and not isinstance(value, str):
        if identity in seen:
            return "[CIRCULAR]"

        seen.add(
            identity
        )

        try:
            sequence_result: list[Any] = [
                sanitize_audit_value(
                    item,
                    _depth=_depth + 1,
                    _force_redact=_force_redact,
                    _seen=seen,
                )
                for item in value[:MAX_ITEMS]
            ]

            if len(value) > MAX_ITEMS:
                sequence_result.append(
                    "[TRUNCATED_ITEMS]"
                )

            return sequence_result
        finally:
            seen.remove(
                identity
            )

    value_type = type(value)
    type_name = (
        f"{value_type.__module__}."
        f"{value_type.__qualname__}"
    )
    unsupported_value = f"[UNSUPPORTED_TYPE:{type_name}]"

    return (
        REDACTED
        if _force_redact
        else _truncate(unsupported_value)
    )


def sanitize_audit_mapping(
        value: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """净化审计映射并确保结果仍为字典."""
    if value is None:
        return None

    result = sanitize_audit_value(
        value
    )

    return result if isinstance(result, dict) else {}
